#!/usr/bin/env python

import argparse
from pathlib import Path
import hashlib

from . import gtfs_dense_pb2
from .parser import parse


def main():
    parser = argparse.ArgumentParser(
        description="Apply a diff to a GTFS-Dense file."
    )
    parser.add_argument(
        "input_file",
        type=Path,
        help="The GTFS-Dense file to patch."
    )
    parser.add_argument(
        "diff_file",
        type=Path,
        help="The diff file to apply."
    )
    parser.add_argument(
        "output_file",
        type=Path,
        help="The path to write the patched file to."
    )
    args = parser.parse_args()

    feed = parse(args.input_file)

    with open(args.diff_file, "rb") as f:
        diff_data = f.read()
        diff = gtfs_dense_pb2.FeedDiff()
        # The checksum is calculated on the whole diff file, so we need to parse it again after the check
        diff.ParseFromString(diff_data)

    patched_feed = apply_patch(feed, diff, diff_data)

    with open(args.output_file, "wb") as f:
        f.write(patched_feed.SerializeToString())

    print(f"Successfully patched file and saved to {args.output_file}")


def apply_patch(feed, diff, diff_data):
    """Applies a FeedDiff to a TransitFeed object."""
    # Verify checksum
    # We need to create a temporary diff object without the checksum to verify it
    temp_diff = gtfs_dense_pb2.FeedDiff()
    temp_diff.CopyFrom(diff)
    temp_diff.header.ClearField("checksum")
    expected_checksum = hashlib.sha256(temp_diff.SerializeToString()).digest()
    if diff.header.checksum != expected_checksum:
        raise ValueError("Diff file checksum does not match.")

    # Verify version
    if diff.header.from_version != feed.header.version:
        raise ValueError(
            f"Diff is for version {diff.header.from_version}, but feed is version {feed.header.version}"
        )

    # Apply additions
    feed.agencies.extend(diff.added_agencies)
    feed.routes.extend(diff.added_routes)
    feed.stops.extend(diff.added_stops)
    feed.shapes.extend(diff.added_shapes)
    feed.calendars.extend(diff.added_calendars)
    feed.calendar_dates.extend(diff.added_calendar_dates)
    feed.trips.extend(diff.added_trips)
    feed.fare_attributes.extend(diff.added_fare_attributes)
    feed.fare_rules.extend(diff.added_fare_rules)
    feed.translations.extend(diff.added_translations)

    # Apply deletions
    for index in sorted(diff.deleted_agencies, reverse=True):
        del feed.agencies[index]
    for index in sorted(diff.deleted_routes, reverse=True):
        del feed.routes[index]
    for index in sorted(diff.deleted_stops, reverse=True):
        del feed.stops[index]
    for index in sorted(diff.deleted_shapes, reverse=True):
        del feed.shapes[index]
    for index in sorted(diff.deleted_calendars, reverse=True):
        del feed.calendars[index]
    for index in sorted(diff.deleted_calendar_dates, reverse=True):
        del feed.calendar_dates[index]
    for index in sorted(diff.deleted_trips, reverse=True):
        del feed.trips[index]
    for index in sorted(diff.deleted_fare_attributes, reverse=True):
        del feed.fare_attributes[index]
    for index in sorted(diff.deleted_fare_rules, reverse=True):
        del feed.fare_rules[index]
    for index in sorted(diff.deleted_translations, reverse=True):
        del feed.translations[index]

    # Apply updates
    for update in diff.updated_agencies:
        feed.agencies[update.index].CopyFrom(update.agency)
    for update in diff.updated_routes:
        feed.routes[update.index].CopyFrom(update.route)
    for update in diff.updated_stops:
        feed.stops[update.index].CopyFrom(update.stop)
    for update in diff.updated_shapes:
        feed.shapes[update.index].CopyFrom(update.shape)
    for update in diff.updated_calendars:
        feed.calendars[update.index].CopyFrom(update.calendar)
    for update in diff.updated_calendar_dates:
        feed.calendar_dates[update.index].CopyFrom(update.calendar_date)
    for update in diff.updated_trips:
        feed.trips[update.index].CopyFrom(update.trip)
    for update in diff.updated_fare_attributes:
        feed.fare_attributes[update.index].CopyFrom(update.fare_attribute)
    for update in diff.updated_fare_rules:
        feed.fare_rules[update.index].CopyFrom(update.fare_rule)
    for update in diff.updated_translations:
        feed.translations[update.index].CopyFrom(update.translation)

    # Update header
    feed.header.version = diff.header.to_version
    feed.header.timestamp = diff.header.timestamp

    return feed


if __name__ == "__main__":
    main()
