import unittest
from pathlib import Path
from gtfsdense import converter

class TestProdFeed(unittest.TestCase):
    def test_nyct_subway(self):
        gtfs_zip_path = Path("test_data/nyct_subway.zip")
        gtfsd_path = Path("test_data/nyct_subway.gtfsd")

        if not gtfs_zip_path.exists():
            self.skipTest("NYCT Subway feed not found. Run `make test_prod` to download it.")

        c = converter.GTFSConverter(gtfs_zip_path)
        c.convert(gtfsd_path)

        self.assertTrue(gtfsd_path.exists())
        self.assertGreater(gtfsd_path.stat().st_size, 0)

if __name__ == '__main__':
    unittest.main()
