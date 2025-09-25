import unittest
import zipfile
from pathlib import Path
from gtfsdense import converter, differ, gtfs_dense_pb2, parser

class TestDiffer(unittest.TestCase):
    def setUp(self):
        self.v1_zip_path = Path("tests/v1.zip")
        self.v1_gtfsd_path = Path("tests/v1.gtfsd")
        self.v2_zip_path = Path("tests/v2.zip")
        self.v2_gtfsd_path = Path("tests/v2.gtfsd")
        self.diff_path = Path("tests/v1_to_v2.gtfsd-diff")

        # Create v1 GTFS
        with zipfile.ZipFile(self.v1_zip_path, 'w') as zf:
            zf.writestr("agency.txt", "agency_id,agency_name,agency_url,agency_timezone\n1,Test Agency,http://test.com,America/New_York\n")
            zf.writestr("routes.txt", "route_id,agency_id,route_short_name,route_long_name,route_type\n1,1,T,Test Route,3\n")
            zf.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\n1,Stop 1,40.7128,-74.0060\n")
            zf.writestr("trips.txt", "route_id,service_id,trip_id,shape_id\n1,1,1,S1\n1,1,2,S2\n")
            zf.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,08:00:00,08:00:00,1,1\n")
            zf.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231\n")
            zf.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nS1,40.7,-74.0,1\nS2,40.8,-74.1,1\n")

        # Create v2 GTFS (updated S1, deleted S2, added S3)
        with zipfile.ZipFile(self.v2_zip_path, 'w') as zf:
            zf.writestr("agency.txt", "agency_id,agency_name,agency_url,agency_timezone\n1,Test Agency,http://test.com,America/New_York\n")
            zf.writestr("routes.txt", "route_id,agency_id,route_short_name,route_long_name,route_type\n1,1,T,Test Route,3\n")
            zf.writestr("stops.txt", "stop_id,stop_name,stop_lat,stop_lon\n1,Stop 1,40.7128,-74.0060\n")
            zf.writestr("trips.txt", "route_id,service_id,trip_id,shape_id\n1,1,1,S1\n1,1,3,S3\n")
            zf.writestr("stop_times.txt", "trip_id,arrival_time,departure_time,stop_id,stop_sequence\n1,08:00:00,08:00:00,1,1\n")
            zf.writestr("calendar.txt", "service_id,monday,tuesday,wednesday,thursday,friday,saturday,sunday,start_date,end_date\n1,1,1,1,1,1,0,0,20250101,20251231\n")
            zf.writestr("shapes.txt", "shape_id,shape_pt_lat,shape_pt_lon,shape_pt_sequence\nS1,40.7,-74.0,1\nS1,40.71,-74.01,2\nS3,40.9,-74.2,1\n")

        # Convert both to gtfsd
        converter.GTFSConverter(self.v1_zip_path).convert(self.v1_gtfsd_path)
        converter.GTFSConverter(self.v2_zip_path).convert(self.v2_gtfsd_path)

    def tearDown(self):
        for p in [self.v1_zip_path, self.v1_gtfsd_path, self.v2_zip_path, self.v2_gtfsd_path, self.diff_path]:
            if p.exists():
                p.unlink()
        for p in [self.v1_gtfsd_path.with_suffix('.shapes.gtfsd-idx'), self.v1_gtfsd_path.with_suffix('.shapes.gtfsd-data'), self.v2_gtfsd_path.with_suffix('.shapes.gtfsd-idx'), self.v2_gtfsd_path.with_suffix('.shapes.gtfsd-data')]:
            if p.exists():
                p.unlink()

    def test_shape_diff(self):
        old_feed = parser.parse(self.v1_gtfsd_path)
        new_feed = parser.parse(self.v2_gtfsd_path)
        old_shapes = differ._load_shapes(self.v1_gtfsd_path)
        new_shapes = differ._load_shapes(self.v2_gtfsd_path)

        diff = differ.create_diff(old_feed, new_feed, old_shapes, new_shapes)

        with open(self.diff_path, 'wb') as f:
            f.write(diff.SerializeToString())

        self.assertTrue(self.diff_path.exists())

        # Parse the diff
        with open(self.diff_path, 'rb') as f:
            diff_from_file = gtfs_dense_pb2.FeedDiff()
            diff_from_file.ParseFromString(f.read())

        self.assertEqual(len(diff_from_file.added_shapes), 1)
        self.assertEqual(diff_from_file.added_shapes[0].shape_id, "S3")

        self.assertEqual(len(diff_from_file.deleted_shapes), 1)
        # S2 was at index 1 in the old feed (sorted order is S1, S2)
        self.assertEqual(diff_from_file.deleted_shapes[0], 1)

        self.assertEqual(len(diff_from_file.updated_shapes), 1)
        # S1 was at index 0 in the old feed
        self.assertEqual(diff_from_file.updated_shapes[0].index, 0)
        self.assertEqual(diff_from_file.updated_shapes[0].shape.shape_id, "S1")
        self.assertNotEqual(diff_from_file.updated_shapes[0].shape.encoded_polyline, old_shapes['S1'].encoded_polyline)

if __name__ == '__main__':
    unittest.main()
