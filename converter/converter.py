import zipfile
import csv
import argparse
from pathlib import Path
import time

# generate ts first pls
# protoc --python_out=. proto/gtfs-dense.proto
from proto import gtfs_dense_pb2
import polyline # For encoding route shapes


def time_to_seconds(time_str):
    try:
        # the GTFS spec allows for hours > 23
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return 0

def yyyymmdd_to_int(date_str):
    try:
        return int(date_str)
    except (ValueError, TypeError):
        return 0

def convert_gtfs_to_dense(gtfs_zip_path: Path, output_path: Path):
    start_time = time.time()
    print(f"Starting conversion of {gtfs_zip_path.name}...")

    feed = gtfs_dense_pb2.TransitFeed()

    route_id_to_index = {}
    stop_id_to_index = {}
    shape_id_to_index = {}
    service_id_to_index = {}

    trip_id_to_trip_message = {}
    shapes_data = {}

    with zipfile.ZipFile(gtfs_zip_path, 'r') as zf:
        file_list = zf.namelist()

        print("-> Processing agency.txt...")
        with zf.open('agency.txt') as f:
            reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
            agency = next(reader, None)
            if agency:
                feed.header.agency_name = agency.get('agency_name', '')
                feed.header.agency_url = agency.get('agency_url', '')
                feed.header.agency_timezone = agency.get('agency_timezone', '')
        feed.header.gtfs_dense_version = "1.0.0"
        feed.header.timestamp = int(time.time())

        print("-> Processing routes.txt...")
        with zf.open('routes.txt') as f:
            reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
            for i, row in enumerate(reader):
                route = feed.routes.add()
                route.route_id = row['route_id']
                route.route_short_name = row.get('route_short_name', '')
                route.route_long_name = row.get('route_long_name', '')
                route.route_type = int(row.get('route_type', 0))
                route.route_color = row.get('route_color', '')
                route.route_text_color = row.get('route_text_color', '')
                route_id_to_index[row['route_id']] = i

        print("-> Processing stops.txt...")
        with zf.open('stops.txt') as f:
            # ... (this part remains the same)
            reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
            for i, row in enumerate(reader):
                stop = feed.stops.add()
                stop.stop_id = row['stop_id']
                stop.stop_name = row.get('stop_name', '')
                stop.lat_e5 = int(float(row.get('stop_lat', 0)) * 1e5)
                stop.lon_e5 = int(float(row.get('stop_lon', 0)) * 1e5)
                stop_id_to_index[row['stop_id']] = i

        if 'calendar.txt' in file_list:
            print("-> Processing calendar.txt...")
            with zf.open('calendar.txt') as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                for i, row in enumerate(reader):
                    # Check if service_id already exists from calendar_dates.txt
                    if row['service_id'] not in service_id_to_index:
                        service_id_to_index[row['service_id']] = len(feed.calendars)
                        calendar = feed.calendars.add()
                        calendar.service_id = row['service_id']
                    else:
                        calendar = feed.calendars[service_id_to_index[row['service_id']]]

                    days_mask = (int(row['monday']) << 0 | int(row['tuesday']) << 1 |
                                 int(row['wednesday']) << 2 | int(row['thursday']) << 3 |
                                 int(row['friday']) << 4 | int(row['saturday']) << 5 |
                                 int(row['sunday']) << 6)
                    calendar.days_mask = days_mask
                    calendar.start_date = yyyymmdd_to_int(row['start_date'])
                    calendar.end_date = yyyymmdd_to_int(row['end_date'])
        else:
            print("-> Skipping calendar.txt (not found).")

        if 'calendar_dates.txt' in file_list:
            print("-> Processing calendar_dates.txt...")
            with zf.open('calendar_dates.txt') as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                for row in reader:
                    cdate = feed.calendar_dates.add()
                    cdate.service_id = row['service_id']
                    cdate.date = yyyymmdd_to_int(row['date'])
                    cdate.exception_type = int(row['exception_type'])
                    if row['service_id'] not in service_id_to_index:
                         service_id_to_index[row['service_id']] = len(service_id_to_index)
        else:
            print("-> Skipping calendar_dates.txt (not found).")

        if 'shapes.txt' in file_list:
            print("-> Processing shapes.txt (grouping points)...")
            with zf.open('shapes.txt') as f:
                reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
                for row in reader:
                    shape_id = row['shape_id']
                    if shape_id not in shapes_data:
                        shapes_data[shape_id] = []
                    shapes_data[shape_id].append(
                        (float(row['shape_pt_lat']), float(row['shape_pt_lon']), int(row['shape_pt_sequence']))
                    )

            print("-> Encoding shapes to polylines...")
            for i, (shape_id, points) in enumerate(shapes_data.items()):
                points.sort(key=lambda p: p[2])
                lat_lon_pairs = [(p[0], p[1]) for p in points]
                shape = feed.shapes.add()
                shape.shape_id = shape_id
                shape.encoded_polyline = polyline.encode(lat_lon_pairs)
                shape_id_to_index[shape_id] = i
        else:
            print("-> Skipping shapes.txt (not found).")

        print("-> Processing trips.txt...")
        with zf.open('trips.txt') as f:
            reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
            for row in reader:
                trip = feed.trips.add()
                trip.trip_id = row['trip_id']
                trip.trip_headsign = row.get('trip_headsign', '')
                trip.route_index = route_id_to_index.get(row['route_id'], 0)

                shape_id = row.get('shape_id')
                if shape_id and shape_id in shape_id_to_index:
                    trip.shape_index = shape_id_to_index[shape_id]

                service_id = row.get('service_id')
                if service_id and service_id in service_id_to_index:
                    trip.service_index = service_id_to_index[service_id]

                trip_id_to_trip_message[row['trip_id']] = trip

        print("-> Processing stop_times.txt (nesting into trips)...")
        with zf.open('stop_times.txt') as f:
            reader = csv.DictReader(f.read().decode('utf-8-sig').splitlines())
            for row in reader:
                trip_message = trip_id_to_trip_message.get(row['trip_id'])
                if trip_message:
                    stop_time = trip_message.stop_times.add()
                    stop_time.stop_index = stop_id_to_index.get(row['stop_id'], 0)
                    stop_time.arrival_time_seconds = time_to_seconds(row.get('arrival_time'))
                    stop_time.departure_time_seconds = time_to_seconds(row.get('departure_time'))

    print("\nSerializing data to binary format...")
    serialized_data = feed.SerializeToString()
    with open(output_path, 'wb') as f:
        f.write(serialized_data)
    end_time = time.time()
    duration = end_time - start_time
    print("Conversion Successful! ^-^")
    print(f"   - Input:  {gtfs_zip_path.name} ({gtfs_zip_path.stat().st_size / 1e6:.2f} MB)")
    print(f"   - Output: {output_path.name} ({output_path.stat().st_size / 1e6:.2f} MB)")
    print(f"   - Time:   {duration:.2f} seconds")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Convert a standard GTFS zip file to a compact GTFS-Dense (.gtfsd) file."
    )
    parser.add_argument(
        "--input",
        type=Path,
        required=True,
        help="Path to the input GTFS .zip file."
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path for the output .gtfsd file."
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: Input file not found at {args.input}")
    else:
        convert_gtfs_to_dense(args.input, args.output)
