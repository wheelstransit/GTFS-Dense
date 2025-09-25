import unittest
import zipfile
from pathlib import Path
from gtfsdense import converter, parser, gtfs_dense_pb2
import polyline

class TestConverter(unittest.TestCase):
    def setUp(self):
        self.gtfs_zip_path = Path("tests/test_data.zip")
        self.gtfsd_path = Path("tests/test_data.gtfsd")
        self.shapes_idx_path = self.gtfsd_path.with_suffix('.shapes.gtfsd-idx')
        self.shapes_data_path = self.gtfsd_path.with_suffix('.shapes.gtfsd-data')

        with zipfile.ZipFile(self.gtfs_zip_path, 'w') as zf:
            zf.writestr("agency.txt", "agency_id,agency_name,agency_url,agency_timezone\n1,Test Agency,http://test.com,America/New_York\n")
            zf.writestr("routes.txt", "route_id,agency_id,route_short_name,route_long_name,route_type\n1,1,T,Test Route,3\n")
            zf.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon,location_type,parent_station\n1,Stop 1,40.7128,-74.0060,0,\n2,Stop 2,40.7138,-74.0070,0,\n3,Station,40.7148,-74.0080,1,\n4,Entrance,40.7158,-74.0090,2,3\n")
            zf.writestr("trips.txt", "route_id,service_id,trip_id,shape_id\n1,1,1,1\n")
            zf.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,08:00:00,08:00:00,1,1\n1,08:05:00,08:05:00,2,2\n")
            zf.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231\n")
            zf.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\n1,40.7128,-74.0060,1\n1,40.7138,-74.0070,2\n")

    def tearDown(self):
        self.gtfs_zip_path.unlink()
        if self.gtfsd_path.exists():
            self.gtfsd_path.unlink()
        if self.shapes_idx_path.exists():
            self.shapes_idx_path.unlink()
        if self.shapes_data_path.exists():
            self.shapes_data_path.unlink()

    def test_converter(self):
        c = converter.GTFSConverter(self.gtfs_zip_path)
        c.convert(self.gtfsd_path)

        self.assertTrue(self.gtfsd_path.exists())

        feed = parser.parse(self.gtfsd_path)

        self.assertEqual(len(feed.agencies), 1)
        self.assertEqual(feed.agencies[0].agency_name, "Test Agency")
        self.assertEqual(len(feed.routes), 1)
        self.assertEqual(feed.routes[0].route_short_name, "T")
        self.assertEqual(len(feed.stops), 4)
        self.assertEqual(feed.stops[0].stop_name, "Stop 1")
        self.assertEqual(feed.stops[3].location_type, 2)
        self.assertEqual(feed.stops[3].parent_station_index, 2)
        self.assertEqual(len(feed.trips), 1)
        self.assertEqual(len(feed.trips[0].stop_times), 2)
        # The trip should have a shape_index pointing to the external shape
        self.assertEqual(feed.trips[0].shape_index, 0)

    def test_shapes_extension(self):
        c = converter.GTFSConverter(self.gtfs_zip_path)
        c.convert(self.gtfsd_path)

        self.assertTrue(self.gtfsd_path.exists())
        self.assertTrue(self.shapes_idx_path.exists())
        self.assertTrue(self.shapes_data_path.exists())

        # Check that the main feed does not contain shapes
        with open(self.gtfsd_path, 'rb') as f:
            transit_feed = gtfs_dense_pb2.TransitFeed()
            transit_feed.ParseFromString(f.read())
            self.assertFalse(hasattr(transit_feed, 'shapes'))

        # Check the shapes index file
        with open(self.shapes_idx_path, 'rb') as f:
            shape_index = gtfs_dense_pb2.ShapeIndex()
            shape_index.ParseFromString(f.read())
            self.assertEqual(len(shape_index.records), 1)
            shape_record = shape_index.records[0]
            self.assertGreater(shape_record.length, 0)

        # Check the shapes data file
        with open(self.shapes_data_path, 'rb') as f:
            f.seek(shape_record.offset)
            shape_bytes = f.read(shape_record.length)
            shape_msg = gtfs_dense_pb2.Shape()
            shape_msg.ParseFromString(shape_bytes)
            self.assertEqual(shape_msg.shape_id, "1")
            decoded_polyline = polyline.decode(shape_msg.encoded_polyline.decode('utf-8'))
            self.assertAlmostEqual(decoded_polyline[0][0], 40.7128)
            self.assertAlmostEqual(decoded_polyline[0][1], -74.0060)
            self.assertAlmostEqual(decoded_polyline[1][0], 40.7138)
            self.assertAlmostEqual(decoded_polyline[1][1], -74.0070)

    def test_converter_ignore_shapes(self):
        c = converter.GTFSConverter(self.gtfs_zip_path, ignore_files=["shapes.txt"])
        c.convert(self.gtfsd_path)

        self.assertTrue(self.gtfsd_path.exists())
        self.assertFalse(self.shapes_idx_path.exists())
        self.assertFalse(self.shapes_data_path.exists())

        feed = parser.parse(self.gtfsd_path)
        self.assertFalse(feed.trips[0].HasField('shape_index'))

if __name__ == '__main__':
    unittest.main()


