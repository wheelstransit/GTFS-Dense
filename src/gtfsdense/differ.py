#!/usr/bin/env python

import argparse
from pathlib import Path
import hashlib

from . import gtfs_dense_pb2
from .parser import parse


def _load_shapes(feed_path: Path) -> dict[str, gtfs_dense_pb2.Shape]:
    """Loads shapes from the shapes extension files."""
    shapes = {}
    shape_idx_path = feed_path.with_suffix('.shapes.gtfsd-idx')
    shape_data_path = feed_path.with_suffix('.shapes.gtfsd-data')

    if not shape_idx_path.exists() or not shape_data_path.exists():
        return shapes

    with open(shape_idx_path, 'rb') as f:
        shape_index = gtfs_dense_pb2.ShapeIndex()
        shape_index.ParseFromString(f.read())

    with open(shape_data_path, 'rb') as f:
        for record in shape_index.records:
            f.seek(record.offset)
            shape_bytes = f.read(record.length)
            shape = gtfs_dense_pb2.Shape()
            shape.ParseFromString(shape_bytes)
            shapes[shape.shape_id] = shape
            
    return shapes


def main():
    parser = argparse.ArgumentParser(
        description="Create a diff between two GTFS-Dense files."
    )
    parser.add_argument(
        "old_file",
        type=Path,
        help="The old GTFS-Dense file."
    )
    parser.add_argument(
        "new_file",
        type=Path,
        help="The new GTFS-Dense file."
    )
    parser.add_argument(
        "output_file",
        type=Path,
        help="The path to write the diff file to."
    )
    args = parser.parse_args()

    old_feed = parse(args.old_file)
    new_feed = parse(args.new_file)

    old_shapes = _load_shapes(args.old_file)
    new_shapes = _load_shapes(args.new_file)

    diff = create_diff(old_feed, new_feed, old_shapes, new_shapes)
    
    serialized_diff = diff.SerializeToString()
    
    # Calculate and add checksum
    checksum = hashlib.sha256(serialized_diff).digest()
    diff.header.checksum = checksum
    
    serialized_diff = diff.SerializeToString()

    with open(args.output_file, "wb") as f:
        f.write(serialized_diff)

    print(f"Successfully created diff file at {args.output_file}")


def create_diff(old_feed, new_feed, old_shapes, new_shapes):
    """Creates a FeedDiff object containing the differences between two TransitFeed objects."""
    diff = gtfs_dense_pb2.FeedDiff()

    # Set header
    diff.header.from_version = old_feed.header.version
    diff.header.to_version = new_feed.header.version
    diff.header.timestamp = new_feed.header.timestamp

    # This is a simplified diff implementation that only handles additions and deletions.
    # It does not handle updates to existing entities, as there is no stable
    # identifier for entities across feed versions. To handle updates, the schema
    # would need to be modified to include a unique ID for each entity.

    # Agencies
    for agency in new_feed.agencies:
        if agency not in old_feed.agencies:
            diff.added_agencies.add().CopyFrom(agency)
    for i, agency in enumerate(old_feed.agencies):
        if agency not in new_feed.agencies:
            diff.deleted_agencies.append(i)

    # Routes
    for route in new_feed.routes:
        if route not in old_feed.routes:
            diff.added_routes.add().CopyFrom(route)
    for i, route in enumerate(old_feed.routes):
        if route not in new_feed.routes:
            diff.deleted_routes.append(i)

    # Stops
    for stop in new_feed.stops:
        if stop not in old_feed.stops:
            diff.added_stops.add().CopyFrom(stop)
    for i, stop in enumerate(old_feed.stops):
        if stop not in new_feed.stops:
            diff.deleted_stops.append(i)

    # Shapes
    old_shape_ids = set(old_shapes.keys())
    new_shape_ids = set(new_shapes.keys())
    
    sorted_old_shape_ids = sorted(list(old_shape_ids))
    old_shape_id_to_index = {shape_id: i for i, shape_id in enumerate(sorted_old_shape_ids)}

    for shape_id in new_shape_ids - old_shape_ids:
        diff.added_shapes.add().CopyFrom(new_shapes[shape_id])

    for shape_id in old_shape_ids - new_shape_ids:
        diff.deleted_shapes.append(old_shape_id_to_index[shape_id])

    for shape_id in old_shape_ids & new_shape_ids:
        old_shape = old_shapes[shape_id]
        new_shape = new_shapes[shape_id]
        if old_shape.encoded_polyline != new_shape.encoded_polyline:
            updated_shape = diff.updated_shapes.add()
            updated_shape.index = old_shape_id_to_index[shape_id]
            updated_shape.shape.CopyFrom(new_shape)

    # Calendars
    for calendar in new_feed.calendars:
        if calendar not in old_feed.calendars:
            diff.added_calendars.add().CopyFrom(calendar)
    for i, calendar in enumerate(old_feed.calendars):
        if calendar not in new_feed.calendars:
            diff.deleted_calendars.append(i)

    # CalendarDates
    for calendar_date in new_feed.calendar_dates:
        if calendar_date not in old_feed.calendar_dates:
            diff.added_calendar_dates.add().CopyFrom(calendar_date)
    for i, calendar_date in enumerate(old_feed.calendar_dates):
        if calendar_date not in new_feed.calendar_dates:
            diff.deleted_calendar_dates.append(i)

    # Trips
    for trip in new_feed.trips:
        if trip not in old_feed.trips:
            diff.added_trips.add().CopyFrom(trip)
    for i, trip in enumerate(old_feed.trips):
        if trip not in new_feed.trips:
            diff.deleted_trips.append(i)

    # FareAttributes
    for fare_attribute in new_feed.fare_attributes:
        if fare_attribute not in old_feed.fare_attributes:
            diff.added_fare_attributes.add().CopyFrom(fare_attribute)
    for i, fare_attribute in enumerate(old_feed.fare_attributes):
        if fare_attribute not in new_feed.fare_attributes:
            diff.deleted_fare_attributes.append(i)

    # FareRules
    for fare_rule in new_feed.fare_rules:
        if fare_rule not in old_feed.fare_rules:
            diff.added_fare_rules.add().CopyFrom(fare_rule)
    for i, fare_rule in enumerate(old_feed.fare_rules):
        if fare_rule not in new_feed.fare_rules:
            diff.deleted_fare_rules.append(i)

    # Translations
    for translation in new_feed.translations:
        if translation not in old_feed.translations:
            diff.added_translations.add().CopyFrom(translation)
    for i, translation in enumerate(old_feed.translations):
        if translation not in new_feed.translations:
            diff.deleted_translations.append(i)

    # Calculate and add checksum
    serialized_diff = diff.SerializeToString()
    checksum = hashlib.sha256(serialized_diff).digest()
    diff.header.checksum = checksum

    return diff


if __name__ == "__main__":
    main()