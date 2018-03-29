# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import csv

# Basic route types (0-7):
#   https://developers.google.com/transit/gtfs/reference/routes-file
# Extended route types (100-1702):
#   https://developers.google.com/transit/gtfs/reference/extended-route-types
route_type_to_text = {
    '0': 'TRAM',
    '1': 'METRO',
    '2': 'RAIL',
    '3': 'BUS',
    '4': 'FERRY',
    '7': 'RAIL',
    '100': 'RAIL',
    '101': 'RAIL',
    '102': 'RAIL',
    '103': 'RAIL',
    '106': 'RAIL',
    '400': 'RAIL',
    '700': 'BUS',
    '900': 'TRAM',
    '1300': 'RAIL',
    '1400': 'RAIL',
    '1501': 'BUS',
    '1700': 'RAIL',
}

# Model from https://developers.google.com/transit/gtfs/reference/
GTFS_MODEL = {
    'agency.txt': {
        'required': True,
        'fields': {
            'agency_id': { 'required': False },
            'agency_name': { 'required': True },
            'agency_url': { 'required': True },
            'agency_timezone': { 'required': True },
            'agency_lang': { 'required': False },
            'agency_phone': { 'required': False },
            'agency_fare_url': { 'required': False },
            'agency_email': { 'required': False },
        },
    },
    'stops.txt': {
        'required': True,
        'fields': {
            'stop_id': { 'required': True },
            'stop_code': { 'required': False },
            'stop_name': { 'required': True },
            'stop_desc': { 'required': False },
            'stop_lat': { 'required': True },
            'stop_lon': { 'required': True },
            'zone_id': { 'required': False },
            'stop_url': { 'required': False },
            'location_type': { 'required': False },
            'parent_station': { 'required': False },
            'stop_timezone': { 'required': False },
            'wheelchair_boarding': { 'required': False },
        },
    },
    'routes.txt': {
        'required': True,
        'fields': {
            'route_id': { 'required': True },
            'agency_id': { 'required': False },
            'route_short_name': { 'required': True },
            'route_long_name': { 'required': True },
            'route_desc': { 'required': False },
            'route_type': { 'required': True },
            'route_url': { 'required': False },
            'route_color': { 'required': False },
            'route_text_color': { 'required': False },
        },
    },
    'trips.txt': {
        'required': True,
        'fields': {
            'route_id': { 'required': True },
            'service_id': { 'required': True },
            'trip_id': { 'required': True },
            'trip_headsign': { 'required': False },
            'trip_short_name': { 'required': False },
            'direction_id': { 'required': False },
            'block_id': { 'required': False },
            'shape_id': { 'required': False },
            'wheelchair_accessible': { 'required': False },
            'bikes_allowed': { 'required': False },
        },
    },
    'stop_times.txt': {
        'required': True,
        'fields': {
            'trip_id': { 'required': True },
            'arrival_time': { 'required': True },
            'departure_time': { 'required': True },
            'stop_id': { 'required': True },
            'stop_sequence': { 'required': True },
            'stop_headsign': { 'required': False },
            'pickup_type': { 'required': False },
            'drop_off_type': { 'required': False },
            'shape_dist_traveled': { 'required': False },
            'timepoint': { 'required': False },
        },
    },
    'calendar.txt': {
        'required': False,
        'fields': {
            'service_id': { 'required': True },
            'monday': { 'required': True },
            'tuesday': { 'required': True },
            'wednesday': { 'required': True },
            'thursday': { 'required': True },
            'friday': { 'required': True },
            'saturday': { 'required': True },
            'sunday': { 'required': True },
            'start_date': { 'required': True },
            'end_date': { 'required': True },
        },
    },
    'calendar_dates.txt': {
        'required': False,
        'fields': {
            'service_id': { 'required': True },
            'date': { 'required': True },
            'exception_type': { 'required': True },
        },
    },
    'fare_attributes.txt': {
        'required': False,
        'fields': {
            'fare_id': { 'required': True },
            'price': { 'required': True },
            'currency_type': { 'required': True },
            'payment_method': { 'required': True },
            'transfers': { 'required': True },
            'transfer_duration': { 'required': False },
        },
    },
    'fare_rules.txt': {
        'required': False,
        'fields': {
            'fare_id': { 'required': True },
            'route_id': { 'required': False },
            'origin_id': { 'required': False },
            'destination_id': { 'required': False },
            'contains_id': { 'required': False },
        },
    },
    'shapes.txt': {
        'required': False,
        'fields': {
            'shape_id': { 'required': True },
            'shape_pt_lat': { 'required': True },
            'shape_pt_lon': { 'required': True },
            'shape_pt_sequence': { 'required': True },
            'shape_dist_traveled': { 'required': True },
            'shape_dist_traveled': { 'required': False },
        },
    },
    'frequencies.txt': {
        'required': False,
        'fields': {
            'trip_id': { 'required': True },
            'start_time': { 'required': True },
            'end_time': { 'required': True },
            'headway_secs': { 'required': True },
            'exact_times': { 'required': False },
        },
    },
    'transfers.txt': {
        'required': False,
        'fields': {
            'from_stop_id': { 'required': True },
            'to_stop_id': { 'required': True },
            'transfer_type': { 'required': True },
            'min_transfer_time': { 'required': False },
        },
    },
    'feed_info.txt': {
        'required': False,
        'fields': {
            'feed_publisher_name': { 'required': True },
            'feed_publisher_url': { 'required': True },
            'feed_lang': { 'required': True },
            'feed_start_date': { 'required': False },
            'feed_end_date': { 'required': False },
            'feed_version': { 'required': False },
       },
    },
}

#===============================================================================
# validate_gtfs_dir ()
#===============================================================================
def validate_gtfs_dir(gtfs_dir):
    files = []
    for (dirpath, dirnames, filenames) in os.walk(gtfs_dir):
        files.extend(filenames)
        break

    gtfs_files_required = [ f for f in GTFS_MODEL if GTFS_MODEL[f]['required'] ]
    files_missing = set(gtfs_files_required) - set(files)
    if files_missing:
        raise FileNotFoundError("Files missing: %s" % ', '.join(files_missing))

    files_parsed = 0

    for filename in sorted(list(set(GTFS_MODEL).intersection(files))):
        print("Validating %s ..." % (filename), file=sys.stderr)
        validate_gtfs_file(filename, gtfs_dir)

#===============================================================================
# parse_gtfs_file ()
#===============================================================================
def parse_gtfs_file(filename, gtfs_dir):
    validate_gtfs_file(filename, gtfs_dir)
    l = []
    with open(os.path.join(gtfs_dir, filename)) as f:
        lines = ( row for row in csv.reader(f, delimiter=',', skipinitialspace=True) )
        field_names = next(lines)  # first line
        field_names[0] = field_names[0].replace(u'\ufeff', '')  # Remove
        for line in lines:
            yield dict(zip(field_names, line))

#===============================================================================
# validate_gtfs_file ()
#===============================================================================
def validate_gtfs_file(filename, gtfs_dir):
    file_path = os.path.join(gtfs_dir, filename)
    if not os.path.isfile(file_path):
        raise FileNotFoundError("[%s]: file not found" % (filename))

    with open(file_path) as f:
        lines = ( row for row in csv.reader(f, delimiter=',', skipinitialspace=True) )
        fields = next(lines)  # first line
        fields[0] = fields[0].replace(u'\ufeff', '')
        gtfs_fields = GTFS_MODEL[filename]['fields']
        gtfs_fields_required = [ f for f in gtfs_fields if gtfs_fields[f]['required'] ]

        # validate all GTFS required fields are present
        fields_missing = set(gtfs_fields_required) - set(fields)
        if fields_missing:
            raise ValueError("[%s] fields missing: %s" % (filename, ', '.join(fields_missing)))

        # validate no unknown field is present
        fields_unknown = set(fields) - set(gtfs_fields)
        if fields_unknown:
            print("[%s] Warning: unknown field(s): %s" % (filename, ', '.join(fields_unknown)), file=sys.stderr)

        for line_num, line in enumerate(lines):
            line_num += 1  # we removed line 0 that contains field names
            values = line
            if len(values) != len(fields):
                if len(values) >= len(fields):
                    raise ValueError("[%s:%d] extra values" % (filename, line_num))

                # validate that if some values are missing, they belong to non-required fields
                fields_of_missing_values = fields[len(values):]
                required_fields_missing = [ f for f in fields_of_missing_values if gtfs_fields[f]['required'] ]
                if required_fields_missing:
                    raise ValueError("[%s:%d] values for required fields missing: %s" %
                       (filename, line_num, ', '.join(required_fields_missing)))
