import os
import sys
import pymongo
import requests
import argparse
import time, datetime, threading
from socialcar.utils import haversine_formula, str_to_oid, oid_to_str, remove_non_ascii
from socialcar.settings import FCM_HOST, FCM_PORT, FCM_API_KEY

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_ETA_NOTIFY_COLLECTION = 'eta_notify'
MONGO_LIFTS_COLLECTION = 'lifts'
MONGO_POSITIONS_COLLECTION = 'positions'
MONGO_USERS_COLLECTION = 'users'

MEAN_VELOCITY = 40

#===============================================================================
# calculate_eta ()
#===============================================================================
def calculate_eta(distance):
    #-----------------------------------------------------------------------
    # Calculate ETA assuming that velocity is 40km/h
    #-----------------------------------------------------------------------
    return int((distance / MEAN_VELOCITY) * 60)

#===============================================================================
# send_push_notification ()
#===============================================================================
def send_push_notification(dbname, user_id, message):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]

    message['type'] = 'eta'
    assert isinstance(message, dict)
    
    user = users_collection.find_one({'_id': user_id})
    fcm_token = user['fcm_token']
    platform = user['platform'] if 'platform' in user else 'ANDROID'

    # if user platform is iOS send custom payload
    if platform == 'IOS':
        platform_url = 'FCMConnectorService/messaging/notification-message/send'
        data_str = '%s' % (message)
        data_str = remove_non_ascii(data_str)
        data_title = "Sample_Title"
        notification_title = "REQUEST_LIFT_TO_DRIVER_TITLE"
        notification_body = "REQUEST_LIFT_TO_DRIVER_BODY"
        data = 'to=%s&api_key=%s&notification_title=%s&notification_body=%s&data_title=%s&data_body=%s' % (fcm_token, FCM_API_KEY, notification_title, notification_body, data_title, data_str)
    elif platform == 'ANDROID':
        platform_url = 'FCMConnectorService/messaging/data-message/send'
        data_str = '%s' % (message)
        data_str = remove_non_ascii(data_str)
        data = 'to=%s&api_key=%s&payload_data=%s' % (fcm_token, FCM_API_KEY, data_str)
        
    url = 'http://%s:%d/%s' % (FCM_HOST, FCM_PORT, platform_url)
    headers = {'content-type': 'application/x-www-form-urlencoded'}
    res = requests.post(url, data=data, headers=headers)
    if res.status_code != 200:
        app.logger.error("Error with notification (%s, \"%s\")" % (url, data))

#===============================================================================
# check_eta_notify ()
#===============================================================================
def check_eta_notify(dbname, radius, period):
    print('%s - Checking for passengers to notify...' % (datetime.datetime.utcnow().strftime('%d-%m-%Y @ %H:%M:%S (UTC)')))

    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    eta_notify_collection = db[MONGO_ETA_NOTIFY_COLLECTION]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    positions_collection = db[MONGO_POSITIONS_COLLECTION]

    cursor1 = eta_notify_collection.find({})
    for item in cursor1:
        driver_pos = None
        lift = lifts_collection.find_one({'_id': item['lift_id']})
        if lift['status'] in ['ACTIVE', 'PENDING']:
            cursor2 = positions_collection.find({'user_id': lift['driver_id']}).sort('timestamp', pymongo.DESCENDING).limit(1)
            for document in cursor2:
                driver_pos = document['point']

            if driver_pos is not None:
                distance = haversine_formula(driver_pos['lon'], driver_pos['lat'], lift['start_point']['point']['lon'], lift['start_point']['point']['lat'])
                time_dif = abs(int(time.time()) - lift['start_point']['date'])
                eta = calculate_eta(distance)
                # Notify passenger if driver is in a radius and time is a period before/after the lift
                if distance <= radius and time_dif <= period:
                    print("    Passenger %s got notified that driver %s is %skm away. Estimated time of arrival: %smin" % (lift['passenger_id'], lift['driver_id'], distance, eta))
                    # TODO: Send push notification here - PushMessagingServer.send(to=passenger_FCM_token, payload_data={'lift_id':lift_id, 'distance':distance ,'eta':eta})
                    send_push_notification(dbname, lift['passenger_id'], {'lift_id': oid_to_str(lift['_id']),'distance':distance ,'eta':eta})
        else:
            eta_notify_collection.remove(item['_id'])

#===============================================================================
# run_periodically ()
#===============================================================================
def run_periodically(interval, dbname, radius, period):
    # This implementation is subject to change
    threading.Timer(interval, run_periodically, args=(interval, dbname, radius, period)).start()
    check_eta_notify(dbname, radius, period)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('-i', '--interval', metavar='INTERVAL', help="Interval to run this script periodically (secs)", type=int, default=600)
    parser.add_argument('-r', '--radius', metavar='RADIUS', help="Send passenger notification within a certain radius from lift start point (kms)", type=int, default=5)
    parser.add_argument('-p', '--period', metavar='PERIOD', help="Send passenger notification within a certain time period from lift start date  (secs)", type=int, default=1800)
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

    radius = args.radius
    period = args.period
    dbname = args.dbname
    interval = args.interval

    print('dbname:      %s' % (dbname))
    print('radius:      %s' % (radius))
    print('period:      %s' % (period))
    print('interval:      %s' % (interval))
    print(' * Passenger ETA Notifier is active! * ')

    run_periodically(interval, dbname, radius, period)

if __name__ == '__main__':
    main()
