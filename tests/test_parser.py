import unittest
from gtfsdense import gtfs_dense_pb2

class TestParser(unittest.TestCase):
    def test_encode_decode(self):
        feed = gtfs_dense_pb2.TransitFeed()
        feed.header.gtfs_dense_version = "1.4.0"

        agency = feed.agencies.add()
        agency.agency_name = "Test Agency"

        serialized_data = feed.SerializeToString()

        new_feed = gtfs_dense_pb2.TransitFeed()
        new_feed.ParseFromString(serialized_data)

        self.assertEqual(new_feed.header.gtfs_dense_version, "1.4.0")
        self.assertEqual(len(new_feed.agencies), 1)
        self.assertEqual(new_feed.agencies[0].agency_name, "Test Agency")

if __name__ == '__main__':
    unittest.main()
