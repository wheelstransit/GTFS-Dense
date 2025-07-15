
import pytest
from pathlib import Path
from gtfsdense.parser import parse
from proto import gtfs_dense_pb2

@pytest.fixture(scope="module")
def parsed_feed():
    """
    A pytest fixture that runs the parser once and provides the result
    to all test functions in this module.
    """
    test_file_path = Path(__file__).parent / "test_feed.gtfsd"
    if not test_file_path.exists():
        pytest.fail(f"Test file not found: {test_file_path}. "
                    "Please generate it using the converter.")

    return parse(test_file_path)

def test_print_feed_overview(parsed_feed: gtfs_dense_pb2.TransitFeed):
    """
    This test prints the main header information and entity counts.
    It acts as a high-level "smoke test" to ensure the file loaded.
    """
    print("\n--- Feed Overview ---")

    assert parsed_feed is not None, "Feed failed to parse and is None."

    # Print Header Info
    header = parsed_feed.header
    print(f"Agency Name: {header.agency_name}")
    print(f"Timezone: {header.agency_timezone}")
    print(f"GTFS-Dense Version: {header.gtfs_dense_version}")

    # Print Entity Counts
    print(f"\nEntity Counts:")
    print(f"  > Routes: {len(parsed_feed.routes)}")
    print(f"  > Stops: {len(parsed_feed.stops)}")
    print(f"  > Trips: {len(parsed_feed.trips)}")
    print(f"  > Shapes: {len(parsed_feed.shapes)}")

    assert len(parsed_feed.routes) > 0, "Feed contains no routes."
    assert len(parsed_feed.stops) > 0, "Feed contains no stops."

def test_inspect_first_route_and_stop(parsed_feed: gtfs_dense_pb2.TransitFeed):
    """
    Inspects the very first route and stop in the lists to verify
    that their data fields are being populated correctly.
    """
    print("\n--- Inspecting First Route and Stop ---")

    # Inspect Route
    first_route = parsed_feed.routes[0]
    print(f"First Route ID: {first_route.route_id}")
    print(f"  > Short Name: {first_route.route_short_name}")
    print(f"  > Long Name: {first_route.route_long_name}")
    print(f"  > Type: {gtfs_dense_pb2.RouteType.Name(first_route.route_type)}")

    # Inspect Stop
    first_stop = parsed_feed.stops[0]
    print(f"\nFirst Stop ID: {first_stop.stop_id}")
    print(f"  > Name: {first_stop.stop_name}")
    print(f"  > Lat (scaled): {first_stop.lat_e5}")
    print(f"  > Lon (scaled): {first_stop.lon_e5}")

def test_inspect_trip_to_route_linking(parsed_feed: gtfs_dense_pb2.TransitFeed):
    """
    This test verifies the critical indexing logic by taking the first trip,
    using its 'route_index' to look up its route, and printing both.
    """
    print("\n--- Inspecting Trip-to-Route Link ---")

    assert len(parsed_feed.trips) > 0, "Feed contains no trips to inspect."

    first_trip = parsed_feed.trips[0]
    print(f"Inspecting Trip ID: {first_trip.trip_id}")
    print(f"  > Headsign: {first_trip.trip_headsign}")
    print(f"  > Route Index: {first_trip.route_index}")

    # This lookup is the actual test of the index
    linked_route = parsed_feed.routes[first_trip.route_index]
    print(f"  > Linked Route Name: {linked_route.route_short_name} - {linked_route.route_long_name}")

def test_inspect_nested_stoptimes(parsed_feed: gtfs_dense_pb2.TransitFeed):
    """
    This test verifies that StopTime messages are correctly nested inside a trip
    and that their 'stop_index' correctly links back to a stop.
    """
    print("\n--- Inspecting Nested StopTimes ---")

    first_trip = parsed_feed.trips[0]
    print(f"Inspecting StopTimes for Trip ID: {first_trip.trip_id}")

    assert len(first_trip.stop_times) > 0, "First trip has no stop times."
    print(f"  > This trip has {len(first_trip.stop_times)} stop times.")

    # Inspect the first StopTime in the list
    first_stop_time = first_trip.stop_times[0]
    print(f"  > First StopTime arrival (seconds from midnight): {first_stop_time.arrival_time_seconds}")

    # Look up the stop using the StopTime's index
    linked_stop = parsed_feed.stops[first_stop_time.stop_index]
    print(f"  > Linked Stop Name: {linked_stop.stop_name}")

def test_inspect_optional_fields(parsed_feed: gtfs_dense_pb2.TransitFeed):
    """
    This test demonstrates how to check for optional fields by inspecting
    the first few trips for a shape_index.
    """
    print("\n--- Inspecting Optional Shape Index ---")

    # Check the first 5 trips
    for i, trip in enumerate(parsed_feed.trips[:5]):
        has_shape = trip.HasField("shape_index")
        shape_index_value = trip.shape_index if has_shape else "N/A"
        print(f"Trip #{i+1} ({trip.trip_id}): Has Shape = {has_shape}, Index = {shape_index_value}")

        if has_shape:
            # If it has a shape, let's also look up the encoded polyline
            linked_shape = parsed_feed.shapes[trip.shape_index]
            print(f"    > Linked Polyline (first 30 chars): {linked_shape.encoded_polyline[:30]}...")
