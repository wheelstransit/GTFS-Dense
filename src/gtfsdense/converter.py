import zipfile
import csv
import argparse
from pathlib import Path
import time
from collections import defaultdict
import io
import tempfile
import os
from typing import Optional

from . import gtfs_dense_pb2
import polyline
from tqdm import tqdm

def _time_to_seconds(time_str):
    """Converts HH:MM:SS to seconds from midnight."""
    try:
        h, m, s = map(int, time_str.split(':'))
        return h * 3600 + m * 60 + s
    except (ValueError, AttributeError):
        return 0

def _yyyymmdd_to_int(date_str):
    """Converts YYYYMMDD string to an integer."""
    try:
        return int(date_str)
    except (ValueError, TypeError):
        return 0

def _format_size(size_bytes):
    """Formats a file size in bytes to a human-readable string."""
    if size_bytes < 1e6:
        return f"{size_bytes / 1e3:.2f} KB"
    else:
        return f"{size_bytes / 1e6:.2f} MB"

class GTFSConverter:
    def __init__(self, gtfs_zip_path: Path, ignore_files: list[str] = None):
        self.gtfs_zip_path = gtfs_zip_path
        self.ignore_files = ignore_files or []
        self.feed = gtfs_dense_pb2.TransitFeed()
        self.agency_id_to_index = {}
        self.route_id_to_index = {}
        self.stop_id_to_index = {}
        self.shape_id_to_index = {}
        self.service_id_to_index = {}
        self.fare_id_to_index = {}
        self.trip_id_to_trip_message = {}
        self.shape_ids = set()
        self.frequencies_data = defaultdict(list)
        self.level_id_to_index = {}
        self.fare_media_id_to_index = {}
        self.rider_category_id_to_index = {}
        self.fare_product_id_to_index = {}
        self.timeframe_group_id_to_index = {}
        self.area_id_to_index = {}
        self.route_index_to_network_id = {}
        self.network_id_to_index = {}
        self.route_network_assignment_keys = set()
        self.leg_group_id_to_index = {}
        self.network_ids_from_routes = set()
        self.stop_area_pairs = set()

    def convert(self, output_path: Path):
        start_time = time.time()
        print(f"Starting conversion of {self.gtfs_zip_path.name}...")

        with zipfile.ZipFile(self.gtfs_zip_path, 'r') as zf:
            self._process_feed_info(zf)
            self._process_agencies(zf)
            self._process_routes(zf)
            self._process_networks(zf)
            self._populate_route_networks_from_routes()
            self._process_route_networks(zf)
            self._process_stops(zf)
            self._process_areas(zf)
            self._process_stop_areas(zf)
            self._process_calendar(zf)
            self._process_calendar_dates(zf)
            self._process_timeframes(zf)
            self._process_shapes(zf)
            self._process_fare_media(zf)
            self._process_rider_categories(zf)
            self._process_fare_products(zf)
            self._process_fare_leg_rules_v2(zf)
            self._process_fare_leg_join_rules(zf)
            self._process_fare_transfer_rules(zf)
            self._process_fare_attributes(zf)
            self._process_fare_rules(zf)
            self._process_frequencies(zf)
            self._process_trips(zf)
            self._process_stop_times(zf)
            self._process_translations(zf)
            self._process_transfers(zf)
            self._process_pathways(zf)
            self._process_levels(zf)

        self._write_shapes_extension(output_path)

        print("\nSerializing data to binary format...")
        serialized_data = self.feed.SerializeToString()
        with open(output_path, 'wb') as f:
            f.write(serialized_data)
        end_time = time.time()
        duration = end_time - start_time
        print("Conversion Successful! ^-^")
        print(f"   - Input:  {self.gtfs_zip_path.name} ({_format_size(self.gtfs_zip_path.stat().st_size)})")
        print(f"   - Output: {output_path.name} ({_format_size(output_path.stat().st_size)})")
        print(f"   - Time:   {duration:.2f} seconds")

    def _read_gtfs_file(self, zf, file_name):
        if file_name in self.ignore_files:
            print(f"-> Ignoring {file_name}...")
            return
        if file_name in zf.namelist():
            print(f"-> Processing {file_name}...")
            with zf.open(file_name) as f:
                # Use TextIOWrapper for memory-efficient CSV reading
                reader = csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))
                yield from reader
        else:
            print(f"-> Skipping {file_name} (not found).")
            return

    def _read_gtfs_file_with_progress(self, zf, file_name):
        """Read GTFS file with progress bar support."""
        if file_name in self.ignore_files:
            print(f"-> Ignoring {file_name}...")
            return [], 0
        if file_name in zf.namelist():
            print(f"-> Processing {file_name}...")
            with zf.open(file_name) as f:
                # First pass: count rows
                content = f.read().decode('utf-8-sig')
                rows = list(csv.DictReader(io.StringIO(content)))
                return rows, len(rows)
        else:
            print(f"-> Skipping {file_name} (not found).")
            return [], 0

    def _process_feed_info(self, zf):
        self.feed.header.gtfs_dense_version = "1.6.0"
        self.feed.header.timestamp = int(time.time())
        for info in self._read_gtfs_file(zf, 'feed_info.txt'):
            self.feed.header.feed_publisher_name = info.get('feed_publisher_name', '')
            self.feed.header.feed_publisher_url = info.get('feed_publisher_url', '')
            self.feed.header.feed_lang = info.get('feed_lang', '')
            self.feed.header.feed_version = info.get('feed_version', '')
            if info.get('feed_start_date'):
                self.feed.header.feed_start_date = _yyyymmdd_to_int(info['feed_start_date'])
            if info.get('feed_end_date'):
                self.feed.header.feed_end_date = _yyyymmdd_to_int(info['feed_end_date'])
            break # feed_info.txt has only one row

    def _process_agencies(self, zf):
        for i, row in enumerate(self._read_gtfs_file(zf, 'agency.txt')):
            agency = self.feed.agencies.add()
            agency.agency_name = row.get('agency_name', '')
            agency.agency_url = row.get('agency_url', '')
            agency.agency_timezone = row.get('agency_timezone', '')
            agency.agency_lang = row.get('agency_lang', '')
            agency.agency_phone = row.get('agency_phone', '')
            agency.agency_fare_url = row.get('agency_fare_url', '')
            if row.get('agency_id'):
                agency.agency_id = row['agency_id']
                self.agency_id_to_index[row['agency_id']] = i

    def _process_routes(self, zf):
        for i, row in enumerate(self._read_gtfs_file(zf, 'routes.txt')):
            route = self.feed.routes.add()
            route.route_short_name = row.get('route_short_name', '')
            route.route_long_name = row.get('route_long_name', '')
            route.route_type = int(row.get('route_type', 0))
            route.route_color = row.get('route_color', '')
            route.route_text_color = row.get('route_text_color', '')
            if row.get('route_id'):
                route.route_id = row['route_id']
                self.route_id_to_index[row['route_id']] = i
            agency_id = row.get('agency_id')
            if agency_id and agency_id in self.agency_id_to_index:
                route.agency_index = self.agency_id_to_index[agency_id]
            network_id = row.get('network_id')
            if network_id:
                route.network_id = network_id
                self.route_index_to_network_id[i] = network_id
                self.network_ids_from_routes.add(network_id)

    def _process_networks(self, zf):
        for row in self._read_gtfs_file(zf, 'networks.txt'):
            network_id = row.get('network_id')
            if not network_id:
                continue
            index = self.network_id_to_index.get(network_id)
            if index is not None:
                network = self.feed.networks[index]
            else:
                network = self.feed.networks.add()
                network.network_id = network_id
                index = len(self.feed.networks) - 1
                self.network_id_to_index[network_id] = index
            if row.get('network_name'):
                network.network_name = row['network_name']

        for network_id in sorted(self.network_ids_from_routes):
            if network_id and network_id not in self.network_id_to_index:
                network = self.feed.networks.add()
                network.network_id = network_id
                self.network_id_to_index[network_id] = len(self.feed.networks) - 1

    def _populate_route_networks_from_routes(self):
        for route_index, network_id in self.route_index_to_network_id.items():
            if not network_id:
                continue
            network_index = self.network_id_to_index.get(network_id)
            if network_index is None:
                continue
            route = self.feed.routes[route_index]
            route.network_index = network_index
            key = (network_index, route_index)
            if key in self.route_network_assignment_keys:
                continue
            assignment = self.feed.route_networks.add()
            assignment.network_index = network_index
            assignment.route_index = route_index
            assignment.network_id = network_id
            assignment.route_id = route.route_id
            self.route_network_assignment_keys.add(key)

    def _process_route_networks(self, zf):
        for row in self._read_gtfs_file(zf, 'route_networks.txt'):
            network_id = row.get('network_id')
            route_id = row.get('route_id')
            if not network_id or not route_id:
                continue
            if network_id not in self.network_id_to_index:
                network = self.feed.networks.add()
                network.network_id = network_id
                self.network_id_to_index[network_id] = len(self.feed.networks) - 1
            network_index = self.network_id_to_index[network_id]
            route_index = self.route_id_to_index.get(route_id)
            if route_index is None:
                continue
            route = self.feed.routes[route_index]
            route.network_index = network_index
            route.network_id = network_id or route.network_id
            key = (network_index, route_index)
            if key in self.route_network_assignment_keys:
                continue
            assignment = self.feed.route_networks.add()
            assignment.network_index = network_index
            assignment.route_index = route_index
            assignment.network_id = network_id
            assignment.route_id = route_id
            self.route_network_assignment_keys.add(key)

    def _process_areas(self, zf):
        for row in self._read_gtfs_file(zf, 'areas.txt'):
            area_id = row.get('area_id')
            if not area_id:
                continue
            if area_id in self.area_id_to_index:
                area = self.feed.areas[self.area_id_to_index[area_id]]
            else:
                area = self.feed.areas.add()
                area.area_id = area_id
                self.area_id_to_index[area_id] = len(self.feed.areas) - 1
            if row.get('area_name'):
                area.area_name = row['area_name']

    def _process_stop_areas(self, zf):
        for row in self._read_gtfs_file(zf, 'stop_areas.txt'):
            area_id = row.get('area_id')
            stop_id = row.get('stop_id')
            if not area_id or not stop_id:
                continue
            if area_id not in self.area_id_to_index:
                area = self.feed.areas.add()
                area.area_id = area_id
                self.area_id_to_index[area_id] = len(self.feed.areas) - 1
            area_index = self.area_id_to_index[area_id]
            stop_index = self.stop_id_to_index.get(stop_id)
            if stop_index is None:
                continue
            pair = (area_index, stop_index)
            if pair in self.stop_area_pairs:
                continue
            stop_area = self.feed.stop_areas.add()
            stop_area.area_index = area_index
            stop_area.stop_index = stop_index
            stop_area.area_id = area_id
            stop_area.stop_id = stop_id
            self.stop_area_pairs.add(pair)

    def _process_timeframes(self, zf):
        for row in self._read_gtfs_file(zf, 'timeframes.txt'):
            group_id = row.get('timeframe_group_id')
            service_id = row.get('service_id')
            if not group_id or not service_id:
                continue
            if service_id not in self.service_id_to_index:
                self.service_id_to_index[service_id] = len(self.feed.calendars)
                placeholder = self.feed.calendars.add()
                placeholder.service_id = service_id
            group_index = self.timeframe_group_id_to_index.get(group_id)
            if group_index is None:
                timeframe_group = self.feed.timeframe_groups.add()
                timeframe_group.timeframe_group_id = group_id
                group_index = len(self.feed.timeframe_groups) - 1
                self.timeframe_group_id_to_index[group_id] = group_index
            else:
                timeframe_group = self.feed.timeframe_groups[group_index]

            window = timeframe_group.windows.add()
            start_time = (row.get('start_time') or '').strip()
            end_time = (row.get('end_time') or '').strip()
            if start_time:
                window.start_time_seconds = _time_to_seconds(start_time)
            if end_time:
                window.end_time_seconds = _time_to_seconds(end_time)
            window.service_index = self.service_id_to_index[service_id]

    def _process_fare_media(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_media.txt'):
            fare_media_id = row.get('fare_media_id')
            if not fare_media_id:
                continue
            index = self.fare_media_id_to_index.get(fare_media_id)
            if index is not None:
                media = self.feed.fare_media[index]
            else:
                media = self.feed.fare_media.add()
                media.fare_media_id = fare_media_id
                index = len(self.feed.fare_media) - 1
                self.fare_media_id_to_index[fare_media_id] = index
            if row.get('fare_media_name'):
                media.fare_media_name = row['fare_media_name']
            media.fare_media_type = int(row.get('fare_media_type', 0) or 0)

    def _process_rider_categories(self, zf):
        for row in self._read_gtfs_file(zf, 'rider_categories.txt'):
            rider_category_id = row.get('rider_category_id')
            if not rider_category_id:
                continue
            index = self.rider_category_id_to_index.get(rider_category_id)
            if index is not None:
                category = self.feed.rider_categories[index]
            else:
                category = self.feed.rider_categories.add()
                category.rider_category_id = rider_category_id
                index = len(self.feed.rider_categories) - 1
                self.rider_category_id_to_index[rider_category_id] = index
            category.rider_category_name = row.get('rider_category_name', '')
            category.is_default_fare_category = bool(int(row.get('is_default_fare_category', 0) or 0))
            if row.get('eligibility_url'):
                category.eligibility_url = row['eligibility_url']

    def _process_fare_products(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_products.txt'):
            fare_product_id = row.get('fare_product_id')
            if not fare_product_id:
                continue
            index = self.fare_product_id_to_index.get(fare_product_id)
            if index is None:
                product = self.feed.fare_products.add()
                product.fare_product_id = fare_product_id
                product.fare_product_name = row.get('fare_product_name', '')
                index = len(self.feed.fare_products) - 1
                self.fare_product_id_to_index[fare_product_id] = index
            else:
                product = self.feed.fare_products[index]
                if row.get('fare_product_name') and not product.fare_product_name:
                    product.fare_product_name = row['fare_product_name']

            price = product.prices.add()
            rider_category_id = row.get('rider_category_id')
            if rider_category_id:
                price.rider_category_id = rider_category_id
                if rider_category_id in self.rider_category_id_to_index:
                    price.rider_category_index = self.rider_category_id_to_index[rider_category_id]
            fare_media_id = row.get('fare_media_id')
            if fare_media_id:
                price.fare_media_id = fare_media_id
                if fare_media_id in self.fare_media_id_to_index:
                    price.fare_media_index = self.fare_media_id_to_index[fare_media_id]
            amount = row.get('amount')
            try:
                price.amount = float(amount) if amount else 0.0
            except ValueError:
                price.amount = 0.0
            price.currency = row.get('currency', '')

    def _ensure_leg_group(self, leg_group_id: Optional[str]) -> Optional[int]:
        if not leg_group_id:
            return None
        index = self.leg_group_id_to_index.get(leg_group_id)
        if index is None:
            leg_group = self.feed.fare_leg_groups.add()
            leg_group.leg_group_id = leg_group_id
            index = len(self.feed.fare_leg_groups) - 1
            self.leg_group_id_to_index[leg_group_id] = index
        return index

    def _process_fare_leg_rules_v2(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_leg_rules.txt'):
            fare_product_id = row.get('fare_product_id')
            if not fare_product_id:
                continue
            fare_product_index = self.fare_product_id_to_index.get(fare_product_id)
            if fare_product_index is None:
                continue
            rule = self.feed.fare_leg_rules_v2.add()
            rule.fare_product_index = fare_product_index
            rule.fare_product_id = fare_product_id

            leg_group_id = row.get('leg_group_id')
            leg_group_index = self._ensure_leg_group(leg_group_id)
            if leg_group_index is not None:
                rule.leg_group_index = leg_group_index
                rule.leg_group_id = leg_group_id

            network_id = row.get('network_id')
            if network_id:
                rule.network_id = network_id
                if network_id not in self.network_id_to_index and network_id:
                    network = self.feed.networks.add()
                    network.network_id = network_id
                    self.network_id_to_index[network_id] = len(self.feed.networks) - 1
                network_index = self.network_id_to_index.get(network_id)
                if network_index is not None:
                    rule.network_index = network_index

            from_area_id = row.get('from_area_id')
            if from_area_id:
                rule.from_area_id = from_area_id
                if from_area_id not in self.area_id_to_index:
                    area = self.feed.areas.add()
                    area.area_id = from_area_id
                    self.area_id_to_index[from_area_id] = len(self.feed.areas) - 1
                rule.from_area_index = self.area_id_to_index[from_area_id]

            to_area_id = row.get('to_area_id')
            if to_area_id:
                rule.to_area_id = to_area_id
                if to_area_id not in self.area_id_to_index:
                    area = self.feed.areas.add()
                    area.area_id = to_area_id
                    self.area_id_to_index[to_area_id] = len(self.feed.areas) - 1
                rule.to_area_index = self.area_id_to_index[to_area_id]

            from_timeframe_group_id = row.get('from_timeframe_group_id')
            if from_timeframe_group_id:
                rule.from_timeframe_group_id = from_timeframe_group_id
                if from_timeframe_group_id in self.timeframe_group_id_to_index:
                    rule.from_timeframe_group_index = self.timeframe_group_id_to_index[from_timeframe_group_id]

            to_timeframe_group_id = row.get('to_timeframe_group_id')
            if to_timeframe_group_id:
                rule.to_timeframe_group_id = to_timeframe_group_id
                if to_timeframe_group_id in self.timeframe_group_id_to_index:
                    rule.to_timeframe_group_index = self.timeframe_group_id_to_index[to_timeframe_group_id]

            if row.get('rule_priority'):
                try:
                    rule.rule_priority = int(row['rule_priority'])
                except ValueError:
                    pass

    def _process_fare_leg_join_rules(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_leg_join_rules.txt'):
            from_network_id = row.get('from_network_id')
            to_network_id = row.get('to_network_id')
            if not from_network_id or not to_network_id:
                continue

            join_rule = self.feed.fare_leg_join_rules.add()
            from_stop_id = row.get('from_stop_id')
            to_stop_id = row.get('to_stop_id')

            if from_network_id:
                join_rule.from_network_id = from_network_id
                if from_network_id not in self.network_id_to_index:
                    network = self.feed.networks.add()
                    network.network_id = from_network_id
                    self.network_id_to_index[from_network_id] = len(self.feed.networks) - 1
                join_rule.from_network_index = self.network_id_to_index[from_network_id]
            if to_network_id:
                join_rule.to_network_id = to_network_id
                if to_network_id not in self.network_id_to_index:
                    network = self.feed.networks.add()
                    network.network_id = to_network_id
                    self.network_id_to_index[to_network_id] = len(self.feed.networks) - 1
                join_rule.to_network_index = self.network_id_to_index[to_network_id]

            if from_stop_id:
                join_rule.from_stop_id = from_stop_id
                if from_stop_id in self.stop_id_to_index:
                    join_rule.from_stop_index = self.stop_id_to_index[from_stop_id]
            if to_stop_id:
                join_rule.to_stop_id = to_stop_id
                if to_stop_id in self.stop_id_to_index:
                    join_rule.to_stop_index = self.stop_id_to_index[to_stop_id]

    def _process_fare_transfer_rules(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_transfer_rules.txt'):
            transfer_rule = self.feed.fare_transfer_rules.add()
            from_leg_group_id = row.get('from_leg_group_id')
            to_leg_group_id = row.get('to_leg_group_id')
            if from_leg_group_id:
                transfer_rule.from_leg_group_id = from_leg_group_id
                index = self._ensure_leg_group(from_leg_group_id)
                if index is not None:
                    transfer_rule.from_leg_group_index = index
            if to_leg_group_id:
                transfer_rule.to_leg_group_id = to_leg_group_id
                index = self._ensure_leg_group(to_leg_group_id)
                if index is not None:
                    transfer_rule.to_leg_group_index = index

            if row.get('transfer_count'):
                try:
                    transfer_rule.transfer_count = int(row['transfer_count'])
                except ValueError:
                    pass
            if row.get('duration_limit'):
                try:
                    transfer_rule.duration_limit = int(row['duration_limit'])
                except ValueError:
                    pass
            if row.get('duration_limit_type'):
                try:
                    transfer_rule.duration_limit_type = int(row['duration_limit_type'])
                except ValueError:
                    pass

            fare_transfer_type = row.get('fare_transfer_type')
            transfer_rule.fare_transfer_type = int(fare_transfer_type or 0)

            fare_product_id = row.get('fare_product_id')
            if fare_product_id:
                transfer_rule.fare_product_id = fare_product_id
                fare_product_index = self.fare_product_id_to_index.get(fare_product_id)
                if fare_product_index is not None:
                    transfer_rule.fare_product_index = fare_product_index
    def _process_stops(self, zf):
        for i, row in enumerate(self._read_gtfs_file(zf, 'stops.txt')):
            stop = self.feed.stops.add()
            stop.stop_name = row.get('stop_name', '')
            stop.lat_e5 = int(float(row.get('stop_lat', 0)) * 1e5)
            stop.lon_e5 = int(float(row.get('stop_lon', 0)) * 1e5)
            stop.zone_id = row.get('zone_id', '')
            stop.location_type = int(row.get('location_type', 0) or 0)
            if row.get('wheelchair_boarding'):
                stop.wheelchair_boarding = bool(int(row['wheelchair_boarding']))
            if row.get('stop_code'):
                stop.stop_code = row['stop_code']
            if row.get('stop_id'):
                stop.stop_id = row['stop_id']
                self.stop_id_to_index[row['stop_id']] = i

        # Second pass to resolve parent stations
        for i, row in enumerate(self._read_gtfs_file(zf, 'stops.txt')):
            parent_station_id = row.get('parent_station')
            if parent_station_id and parent_station_id in self.stop_id_to_index:
                self.feed.stops[i].parent_station_index = self.stop_id_to_index[parent_station_id]

    def _process_calendar(self, zf):
        for row in self._read_gtfs_file(zf, 'calendar.txt'):
            service_id = row['service_id']
            if service_id not in self.service_id_to_index:
                self.service_id_to_index[service_id] = len(self.feed.calendars)
                calendar = self.feed.calendars.add()
                calendar.service_id = service_id
            else:
                calendar = self.feed.calendars[self.service_id_to_index[service_id]]
                if not calendar.service_id:
                    calendar.service_id = service_id

            days_mask = (int(row['monday']) << 0 | int(row['tuesday']) << 1 |
                         int(row['wednesday']) << 2 | int(row['thursday']) << 3 |
                         int(row['friday']) << 4 | int(row['saturday']) << 5 |
                         int(row['sunday']) << 6)
            calendar.days_mask = days_mask
            calendar.start_date = _yyyymmdd_to_int(row['start_date'])
            calendar.end_date = _yyyymmdd_to_int(row['end_date'])

    def _process_calendar_dates(self, zf):
        for row in self._read_gtfs_file(zf, 'calendar_dates.txt'):
            service_id = row['service_id']
            if service_id not in self.service_id_to_index:
                self.service_id_to_index[service_id] = len(self.feed.calendars)
                placeholder = self.feed.calendars.add() # Add a placeholder calendar
                placeholder.service_id = service_id

            cdate = self.feed.calendar_dates.add()
            cdate.service_index = self.service_id_to_index[service_id]
            cdate.date = _yyyymmdd_to_int(row['date'])
            cdate.exception_type = int(row['exception_type'])

    def _process_shapes(self, zf):
        if 'shapes.txt' in self.ignore_files:
            print(f"-> Ignoring shapes.txt...")
            return
        if 'shapes.txt' not in zf.namelist():
            print(f"-> Skipping shapes.txt (not found).")
            return

        print(f"-> Processing shapes.txt...")

        # Stream through file to collect unique shape IDs with minimal memory usage
        with zf.open('shapes.txt') as f:
            reader = csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))

            row_count = 0
            for row in reader:
                row_count += 1
                shape_id = row['shape_id']
                self.shape_ids.add(shape_id)

                # Progress update every 500k rows
                if row_count % 500000 == 0:
                    print(f"   Scanned {row_count:,} shape points, found {len(self.shape_ids)} unique shapes so far...")

        print(f"   Scanned {row_count:,} total shape points, found {len(self.shape_ids)} unique shapes")

        # Shape records will be created during write phase
        print(f"   Found {len(self.shape_ids)} unique shapes")

    def _write_shapes_extension(self, output_path: Path):
        if not self.shape_ids:
            print("-> No shapes data found, skipping shapes extension files.")
            return

        print("\nGenerating shapes extension files...")
        shapes_idx_path = output_path.with_suffix('.shapes.gtfsd-idx')
        shapes_data_path = output_path.with_suffix('.shapes.gtfsd-data')

        shape_index_msg = gtfs_dense_pb2.ShapeIndex()
        sorted_shape_ids = sorted(self.shape_ids)

        print(f"   Processing {len(sorted_shape_ids):,} shapes with disk-based streaming...")

        # Create temp directory for shape data files
        temp_dir = tempfile.mkdtemp()
        temp_files = {}

        try:
            # Single pass: stream through shapes.txt and write to temp files
            with zipfile.ZipFile(self.gtfs_zip_path, 'r') as zf:
                with zf.open('shapes.txt') as f:
                    reader = csv.DictReader(io.TextIOWrapper(f, "utf-8-sig"))

                    row_count = 0
                    for row in reader:
                        row_count += 1
                        shape_id = row['shape_id']

                        if shape_id in self.shape_ids:
                            # Create temp file for this shape if not exists
                            if shape_id not in temp_files:
                                temp_file_path = os.path.join(temp_dir, f"shape_{len(temp_files)}.tmp")
                                temp_files[shape_id] = open(temp_file_path, 'w')

                            # Write point data to temp file
                            temp_files[shape_id].write(f"{row['shape_pt_lat']},{row['shape_pt_lon']},{row['shape_pt_sequence']}\n")

                        # Progress update every 1M rows for large files
                        if row_count % 1000000 == 0:
                            print(f"   Processed {row_count:,} shape points...")

            # Close all temp files
            for f in temp_files.values():
                f.close()

            print(f"   Completed reading {row_count:,} shape points")
            print(f"   Encoding {len(sorted_shape_ids):,} shapes to binary format...")

            # Process shapes in sorted order
            with open(shapes_data_path, 'wb') as f_data:
                progress_bar = tqdm(sorted_shape_ids, desc="   Encoding shapes", unit="shapes")

                for shape_id in progress_bar:
                    if shape_id in temp_files:
                        # Read points from temp file
                        points = []
                        temp_file_path = temp_files[shape_id].name

                        with open(temp_file_path, 'r') as tf:
                            for line in tf:
                                lat, lon, seq = line.strip().split(',')
                                points.append((float(lat), float(lon), int(seq)))

                        # Sort by sequence and create lat/lon pairs
                        points.sort(key=lambda p: p[2])
                        lat_lon_pairs = [(p[0], p[1]) for p in points]

                        # Encode and write shape
                        shape_msg = gtfs_dense_pb2.Shape()
                        shape_msg.shape_id = shape_id
                        shape_msg.encoded_polyline = polyline.encode(lat_lon_pairs).encode('utf-8')

                        serialized_shape = shape_msg.SerializeToString()

                        offset = f_data.tell()
                        length = f_data.write(serialized_shape)

                        record = shape_index_msg.records.add()
                        record.offset = offset
                        record.length = length
                        record.shape_id = shape_id

                        # Store index for later lookup in trips
                        self.shape_id_to_index[shape_id] = len(shape_index_msg.records) - 1

        finally:
            # Clean up temporary files
            for shape_id, temp_file in temp_files.items():
                try:
                    if hasattr(temp_file, 'name') and os.path.exists(temp_file.name):
                        os.unlink(temp_file.name)
                except:
                    pass
            try:
                os.rmdir(temp_dir)
            except:
                pass

        with open(shapes_idx_path, 'wb') as f_idx:
            f_idx.write(shape_index_msg.SerializeToString())

        print(f"   - Index:  {shapes_idx_path.name} ({_format_size(shapes_idx_path.stat().st_size)})")
        print(f"   - Data:   {shapes_data_path.name} ({_format_size(shapes_data_path.stat().st_size)})")

    def _process_fare_attributes(self, zf):
        for i, row in enumerate(self._read_gtfs_file(zf, 'fare_attributes.txt')):
            fare = self.feed.fare_attributes.add()
            fare.price = float(row.get('price', 0))
            fare.currency_type = row.get('currency_type', '')
            fare.payment_method = int(row.get('payment_method', 0))
            fare.transfers = 99 if row.get('transfers') == '' else int(row.get('transfers', 0))
            if row.get('transfer_duration'):
                fare.transfer_duration = int(row['transfer_duration'])
            self.fare_id_to_index[row['fare_id']] = i

    def _process_fare_rules(self, zf):
        for row in self._read_gtfs_file(zf, 'fare_rules.txt'):
            rule = self.feed.fare_rules.add()
            rule.fare_attribute_index = self.fare_id_to_index.get(row['fare_id'], 0)
            if row.get('route_id'):
                rule.route_index = self.route_id_to_index.get(row['route_id'])
            rule.origin_id = row.get('origin_id', '')
            rule.destination_id = row.get('destination_id', '')
            rule.contains_id = row.get('contains_id', '')

    def _process_frequencies(self, zf):
        for row in self._read_gtfs_file(zf, 'frequencies.txt'):
            freq_data = {
                "start_time": _time_to_seconds(row['start_time']),
                "end_time": _time_to_seconds(row['end_time']),
                "headway_secs": int(row['headway_secs']),
                "exact_times": int(row.get('exact_times', 0))
            }
            self.frequencies_data[row['trip_id']].append(freq_data)

    def _process_trips(self, zf):
        for row in self._read_gtfs_file(zf, 'trips.txt'):
            trip = self.feed.trips.add()
            trip_id = row['trip_id']
            trip.trip_id = trip_id
            trip.trip_headsign = row.get('trip_headsign', '')
            route_id = row.get('route_id')
            if route_id and route_id in self.route_id_to_index:
                trip.route_index = self.route_id_to_index[route_id]
            else:
                trip.route_index = 0

            shape_id = row.get('shape_id')
            if shape_id and shape_id in self.shape_id_to_index:
                trip.shape_index = self.shape_id_to_index[shape_id]
                trip.shape_id = shape_id
            elif shape_id:
                trip.shape_id = shape_id

            service_id = row.get('service_id')
            if service_id and service_id in self.service_id_to_index:
                trip.service_index = self.service_id_to_index[service_id]

            if row.get('trip_short_name'):
                trip.trip_short_name = row['trip_short_name']

            if row.get('bikes_allowed'):
                trip.bikes_allowed = bool(int(row['bikes_allowed']))

            if row.get('wheelchair_accessible'):
                trip.wheelchair_accessible = bool(int(row['wheelchair_accessible']))

            if row.get('direction_id'):
                trip.direction_id = bool(int(row['direction_id']))

            if row.get('block_id'):
                trip.block_id = row['block_id']

            self.trip_id_to_trip_message[trip_id] = trip

            if trip_id in self.frequencies_data:
                for freq_data in self.frequencies_data[trip_id]:
                    freq_msg = trip.frequencies.add()
                    freq_msg.start_time_seconds = freq_data['start_time']
                    freq_msg.end_time_seconds = freq_data['end_time']
                    freq_msg.headway_secs = freq_data['headway_secs']
                    freq_msg.exact_times = freq_data['exact_times']

    def _process_stop_times(self, zf):
        stop_times_data = defaultdict(list)
        for row in self._read_gtfs_file(zf, 'stop_times.txt'):
            stop_times_data[row['trip_id']].append(row)

        for trip_id, stop_time_rows in stop_times_data.items():
            trip_message = self.trip_id_to_trip_message.get(trip_id)
            if trip_message:
                # Sort stop times by stop_sequence before adding them
                stop_time_rows.sort(key=lambda r: int(r['stop_sequence']))
                for row in stop_time_rows:
                    stop_time = trip_message.stop_times.add()
                    stop_time.stop_index = self.stop_id_to_index.get(row['stop_id'], 0)
                    stop_time.arrival_time_seconds = _time_to_seconds(row.get('arrival_time'))
                    stop_time.departure_time_seconds = _time_to_seconds(row.get('departure_time'))
                    stop_time.stop_sequence = int(row.get('stop_sequence', 0))
                    if row.get('stop_headsign'):
                        stop_time.stop_headsign = row['stop_headsign']

    def _process_translations(self, zf):
        for row in self._read_gtfs_file(zf, 'translations.txt'):
            trans = self.feed.translations.add()
            trans.table_name = row.get('table_name', '')
            trans.field_name = row.get('field_name', '')
            trans.language = row.get('language', '')
            trans.translation = row.get('translation', '')
            trans.record_id = row.get('record_id', '')

    def _process_transfers(self, zf):
        for row in self._read_gtfs_file(zf, 'transfers.txt'):
            transfer = self.feed.transfers.add()
            transfer.from_stop_index = self.stop_id_to_index.get(row['from_stop_id'], 0)
            transfer.to_stop_index = self.stop_id_to_index.get(row['to_stop_id'], 0)
            transfer.type = int(row.get('transfer_type', 0) or 0)
            if row.get('min_transfer_time'):
                transfer.min_transfer_time = int(row['min_transfer_time'])

    def _process_pathways(self, zf):
        for row in self._read_gtfs_file(zf, 'pathways.txt'):
            pathway = self.feed.pathways.add()
            pathway.pathway_id = row.get('pathway_id', '')
            pathway.from_stop_index = self.stop_id_to_index.get(row['from_stop_id'], 0)
            pathway.to_stop_index = self.stop_id_to_index.get(row['to_stop_id'], 0)
            pathway.pathway_mode = int(row.get('pathway_mode', 0) or 0)
            pathway.is_bidirectional = bool(int(row.get('is_bidirectional', 0) or 0))
            if row.get('length'):
                pathway.length = float(row['length'])
            if row.get('traversal_time'):
                pathway.traversal_time = int(row['traversal_time'])
            if row.get('stair_count'):
                pathway.stair_count = int(row['stair_count'])
            if row.get('max_slope'):
                pathway.max_slope = float(row['max_slope'])
            if row.get('min_width'):
                pathway.min_width = float(row['min_width'])
            pathway.signposted_as = row.get('signposted_as', '')
            pathway.reversed_signposted_as = row.get('reversed_signposted_as', '')

    def _process_levels(self, zf):
        for i, row in enumerate(self._read_gtfs_file(zf, 'levels.txt')):
            level = self.feed.levels.add()
            level.level_id = row.get('level_id', '')
            level.level_index = float(row.get('level_index', 0))
            level.level_name = row.get('level_name', '')
            self.level_id_to_index[row['level_id']] = i


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
    parser.add_argument(
        "--ignore",
        type=str,
        nargs="*",
        help="List of GTFS files to ignore (e.g., shapes.txt)."
    )
    args = parser.parse_args()

    if not args.input.is_file():
        print(f"Error: Input file not found at {args.input}")
    else:
        converter = GTFSConverter(args.input, args.ignore)
        converter.convert(args.output)
