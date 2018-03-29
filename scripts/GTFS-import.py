# -*- coding: utf-8 -*-
from __future__ import print_function
import os
import sys
import csv
import json
import argparse
import tempfile
import zipfile
import shutil
import pymongo
from collections import defaultdict
from gtfs import parse_gtfs_file, validate_gtfs_file, route_type_to_text

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_STOPS_COLLECTION = 'stops'
MONGO_DEPARTURES_COLLECTION = 'departures'

PERIODIC_PRINT = 1000

#===============================================================================
# import_gtfs_dir ()
#===============================================================================
def import_gtfs_dir(gtfs_dir, dbname):

    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    stops_collection = db[MONGO_STOPS_COLLECTION]
    departures_collection = db[MONGO_DEPARTURES_COLLECTION]

    # Disable acknowledgement of write operations to speed up inserts/updates
    wconcert = pymongo.write_concern.WriteConcern(w=0)
    stops_collection = stops_collection.with_options(write_concern=wconcert)
    departures_collection = departures_collection.with_options(write_concern=wconcert)

    # Add indices, if they don't exist
    stops_collection.create_index('stop_code', unique=True)
    stops_collection.create_index([ ('loc', pymongo.GEOSPHERE) ])
    departures_collection.create_index('stop_code', unique=True)

    try:
        #-----------------------------------------------------------------------
        # 1. Create mapping: stop_id -> { lat, long, stop_code, stop_name }
        #-----------------------------------------------------------------------
        stops = {}
        print("Parsing stops.txt...")
        for row in parse_gtfs_file('stops.txt', gtfs_dir):
            stops[row['stop_id']] = {
                'loc': {
                    'type': 'Point',
                    'coordinates': [
                        float(row['stop_lon']),
                        float(row['stop_lat']),
                    ]
                },
                'stop_code': row['stop_id'],
                'stop_name': row['stop_name'],
                'transits': {}
            }

        #-----------------------------------------------------------------------
        # 2. Create mapping: route_id -> { route_type, short_name, long_name }
        #-----------------------------------------------------------------------
        routes = {}
        print("Parsing routes.txt...")
        for row in parse_gtfs_file('routes.txt', gtfs_dir):
            routes[row['route_id']] = {
                'travel_mode': route_type_to_text[row['route_type']],
                'short_name': row['route_short_name'],
                'long_name': row['route_long_name'],
            }

        #-----------------------------------------------------------------------
        # 3. Create mapping: trip_id -> route_id
        #-----------------------------------------------------------------------
        print("Parsing trips.txt...")
        trips = {}
        for row in parse_gtfs_file('trips.txt', gtfs_dir):
            trips[row['trip_id']] = row['route_id']

        #-----------------------------------------------------------------------
        # 4. Create mapping: stop_id -> trip_id =>
        #                    stop_id -> route_id =>
        #                    stop_id -> { route_type, short_name, long_name }
        #    and mapping:    stop_id -> { route_id: [ departure times ] }
        #-----------------------------------------------------------------------
        print("Parsing stop_times.txt...")
        departures = defaultdict(dict)
        for row in parse_gtfs_file('stop_times.txt', gtfs_dir):
            stop_id = row['stop_id']
            trip_id = row['trip_id']
            route_id = trips[trip_id]
            transit = routes[route_id]  # transit = route
            # short_name: unique key for transits
            route_short_name = transit['short_name']
            route_short_name = route_short_name.replace('.', '_')  # MongoDB keys cannot contain '.'
            stops[stop_id]['transits'].update({route_short_name: transit})

            # stop_id -> { route_id: [ departure times ] }
            if route_id not in departures[stop_id]:
                departures[stop_id][route_id] = set()
            # assert row['departure_time'] not in departures[stop_id][route_id]
            time = row['departure_time']
            # '6:13:00' -> '06:13:00'
            if len(time) != 8:
                time = ':'.join([ "%02d" % int(v) for v in time.split(':') ])
            departures[stop_id][route_id].add(time)

        # Sort departure times
        for stop_departures in departures.values():
            for route_id in stop_departures:
                stop_departures[route_id] = sorted(stop_departures[route_id])

        #-----------------------------------------------------------------------
        # 5. Insert stops into database
        #-----------------------------------------------------------------------
        print("Insert stops into database...")
        inserted, updated = 0, 0
        for stop in stops.values():
            # stop = {
            #     'stop_code': <stop_code>,
            #     'stop_name': <stop_name>,
            #     'loc': { 'type': 'Point', 'coordinates': [ <lon>, <lat> ] },
            #     'transits': [
            #         {
            #             'transport': {
            #                 'short_name':  <route_short_name>,
            #                 'long_name':   <route_long_name>,
            #                 'travel_mode': <route_travel_mode>,
            #             }
            #         }
            #         ...
            #     ]
            # }

            # dict { short_name -> {data} } -> list [ 'transport': {data} ]
            stop['transits'] = [ {'transport': v} for v in stop['transits'].values() ]
            try:
                stops_collection.insert(stop)
                inserted += 1
            except pymongo.errors.DuplicateKeyError:
                # Stop already exists: just add new transits
                lookup = { 'stop_code': stop['stop_code'] }
                update = { '$addToSet': { 'transits': { '$each': stop['transits'] } } }
                stops_collection.update(lookup, update)
                updated += 1

            if (inserted + updated) % PERIODIC_PRINT == 0:
                print('%d records inserted, %d records updated' % (inserted, updated))
        print('%d records inserted, %d records updated' % (inserted, updated))

        #-----------------------------------------------------------------------
        # 6. Insert departure times into database
        #-----------------------------------------------------------------------
        print("Insert departure times into database...")
        inserted, updated = 0, 0
        for stop_id in departures:
            # stop_departures = {
            #     'stop_code': <stop_code>,
            #     'transits': {
            #         <route_short_name>: [ <t1> .. <tN> ]
            #         <route_short_name>: [ <t1> .. <tK> ]
            #     }
            # }
            stop_departures = {
                'stop_code': stop_id,
                'transits': {}
            }
            for route_id in departures[stop_id]:
                route_short_name = routes[route_id]['short_name']
                route_short_name = route_short_name.replace('.', '_')  # MongoDB keys cannot contain '.'
                stop_departures['transits'].update({
                    route_short_name: departures[stop_id][route_id]
                })
            try:
                departures_collection.insert(stop_departures)
                inserted += 1
            except pymongo.errors.DuplicateKeyError:
                # Stop already exists: just add departure times for new transits
                lookup = { 'stop_code': stop['stop_code'] }
                update = { '$addToSet': { 'transits': stop_departures['transits'] } }
                stops_collection.update(lookup, update, {'j': 'false'})
                updated += 1

            if (inserted + updated) % PERIODIC_PRINT == 0:
                print('%d records inserted, %d records updated' % (inserted, updated))
        print('%d records inserted, %d records updated' % (inserted, updated))


    except (FileNotFoundError, ValueError) as e:
        print(e)
        sys.exit(1)


#===============================================================================
# error ()
#===============================================================================
def error(msg):
    print(msg)
    sys.exit(1)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-f', metavar='FILE', help="zip file containg GTFS files", type=str)
    parser.add_argument('-d', metavar='DIR', help="directory containg GTFS files", type=str)
    parser.add_argument('dbname', metavar='DBNAME', help="Database name", type=str)
    return parser

#===============================================================================
# main ()
#===============================================================================
def main():

    parser = create_arg_parser()
    # If script run without arguments, print syntax
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    dbname = args.dbname

    if (not args.f and not args.d) or (args.f and args.d):
        error("Specify either a file (-f) or folder (-d) containg the GTFS files.")

    # If user specified a directory that contains GTFS files:
    if args.d:
        gtfs_dir = args.d
        if not os.path.isdir(gtfs_dir):
            error("Directory '%s' not found." % gtfs_dir)
        import_gtfs_dir(gtfs_dir, dbname)
    # Else, user specified a zip file that contains GTFS files:
    else:
        gtfs_file = args.f
        if not os.path.isfile(gtfs_file):
            error("File '%s' not found." % gtfs_file)
        tempdir = tempfile.mkdtemp()
        try:
            with zipfile.ZipFile(gtfs_file, 'r') as zipf:
                zipf.extractall(tempdir)
                import_gtfs_dir(tempdir, dbname)
        finally:
            shutil.rmtree(tempdir)

if __name__ == '__main__':
    main()
