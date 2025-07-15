from pathlib import Path
from proto import gtfs_dense_pb2

def parse(filepath: Path) -> gtfs_dense_pb2.TransitFeed:
    feed = gtfs_dense_pb2.TransitFeed()

    with open(filepath, "rb") as f:
        binary_data = f.read()
        feed.ParseFromString(binary_data)

    return feed
