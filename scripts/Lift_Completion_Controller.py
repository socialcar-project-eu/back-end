import os
import sys
import pymongo
import argparse
import time, datetime, threading

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_LIFTS_COLLECTION = 'lifts'

#===============================================================================
# check_lift_completion ()
#===============================================================================
def check_lift_completion(dbname):
    print('%s - Checking for active lifts...' % (datetime.datetime.utcnow().strftime('%d-%m-%Y @ %H:%M:%S (UTC)')))

    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]

    current_time = int(time.time())
    cursor = lifts_collection.find({"status":"ACTIVE"})
    for lift in cursor:
        if lift['end_point']['date'] <= current_time:
            print("    Lift %s status changed to 'COMPLETED'" % (lift['_id']))
            lifts_collection.update({'_id': lift['_id']}, {'$set': {'status': 'COMPLETED'}}, upsert = False)

#===============================================================================
# run_periodically ()
#===============================================================================
def run_periodically(interval, dbname):
    # This implementation is subject to change
    threading.Timer(interval, run_periodically, args=(interval, dbname)).start()
    check_lift_completion(dbname)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--interval', metavar='INTERVAL', help="Interval to run this script periodically (secs)", type=int, default=60)
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
    interval = args.interval

    print('dbname:      %s' % (dbname))
    print('interval:      %s' % (interval))
    print(' * Lift Completion Service is active! * ')

    run_periodically(interval, dbname)

if __name__ == '__main__':
    main()
