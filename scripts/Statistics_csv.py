import os
import sys
import pymongo
import time, datetime
import csv
from operator import itemgetter

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_USERS_COLLECTION = 'users'
MONGO_RIDES_COLLECTION = 'rides'
MONGO_LIFTS_COLLECTION = 'lifts'
MONGO_FEEDBACKS_COLLECTION = 'feedbacks'
MONGO_SITES_COLLECTION = 'sites'
STATISTICS_SCRIPT_FOLDER = os.path.dirname(os.path.realpath(__file__))

#===============================================================================
# user_activity_csv ()
#===============================================================================
def user_activity_csv(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    rides_collection = db[MONGO_RIDES_COLLECTION]
    sites_collection = db[MONGO_SITES_COLLECTION]
    period = datetime.datetime.utcnow()-datetime.timedelta(days=30)
    csv_list = []

    cursor_sites = sites_collection.find({}, { 'bounding_box': 1, 'name': 1 })
    cursor_users = users_collection.find({ 'email': { '$ne': 'driver@rdex.com' } }, { '_id': 1, 'name': 1, 'email': 1 })

    # store total users
    users = []
    for user in cursor_users:
        users.append(user)

    csv_list.append(['User', 'lifts offered W1', 'lifts offered W2', 'lifts offered W3', 'lifts offered W4', 'Total offered', 'lifts requested W1', 'lifts requested W2', 'lifts requested W3', 'lifts requested W4', 'Total requested', 'site'])

    # For every site in db
    for site in cursor_sites:
        
        bb_minlat = site['bounding_box']['min_lat']
        bb_minlon = site['bounding_box']['min_lon']
        bb_maxlat = site['bounding_box']['max_lat']
        bb_maxlon = site['bounding_box']['max_lon']

        lookup_lifts1 = { '$and': [ { 'end_point.point.lat': { '$gte': bb_minlat } } , \
                            { 'end_point.point.lat': { '$lte': bb_maxlat } } , \
                            { 'end_point.point.lon': { '$gte': bb_minlon } } , \
                            { 'end_point.point.lon': { '$lte': bb_maxlon } } ] }
        lookup_lifts2 = { '$and': [ {'start_point.point.lat': {'$gte': bb_minlat } } , \
                            { 'start_point.point.lat': { '$lte': bb_maxlat } } , \
                            { 'start_point.point.lon': { '$gte': bb_minlon } } , \
                            { 'start_point.point.lon': { '$lte': bb_maxlon } } ] }
        lookup_lifts = { '$or': [ lookup_lifts1, lookup_lifts2 ] }

        lookup_rides1 = { '$and': [ {'end_point.lat': { '$gte': bb_minlat } } , \
                            { 'end_point.lat': { '$lte': bb_maxlat } } , \
                            { 'end_point.lon': { '$gte': bb_minlon } } , \
                            { 'end_point.lon': { '$lte': bb_maxlon } } ] }
        lookup_rides2 = { '$and': [ {'start_point.lat': {'$gte': bb_minlat } } , \
                            { 'start_point.lat': { '$lte': bb_maxlat } } , \
                            { 'start_point.lon': { '$gte': bb_minlon } } , \
                            { 'start_point.lon': { '$lte': bb_maxlon } } ] }
        lookup_rides = { '$and': [ { 'lifts': { '$eq': [] } }, { '$or': [ lookup_rides1, lookup_rides2 ] } ] }

        cursor_lifts = lifts_collection.find(lookup_lifts, { 'driver_id' : 1 , 'passenger_id' : 1 , 'status' : 1 , '_updated' : 1})
        cursor_rides = rides_collection.find(lookup_rides, { 'driver_id': 1, '_updated' : 1 })

        # store total lifts
        lifts = []
        for lift in cursor_lifts:
            lifts.append(lift)

        # store total rides
        rides = []
        for ride in cursor_rides:
            rides.append(ride)
        
        for user in users:
            # store user lifts
            user_lifts = []
            for lift in lifts:
                if lift['driver_id'] == user['_id'] or lift['passenger_id'] == user['_id']:
                    user_lifts.append(lift)

            # store user rides
            user_rides = []
            for ride in rides:
                if ride['driver_id'] == user['_id']:
                    user_rides.append(ride)
            
            rides_num = len(user_rides)
            lifts_num = 0
            rides_completed_num = 0
            rides_pending_num = len(user_rides)
            rides_active_num = 0
            rides_refused_num = 0
            rides_cancelled_num = 0
            lifts_completed_num = 0
            lifts_pending_num = 0
            lifts_active_num = 0
            lifts_refused_num = 0
            lifts_cancelled_num = 0
            lifts_week1_dr = 0
            lifts_week2_dr = 0
            lifts_week3_dr = 0
            lifts_week4_dr = 0
            lifts_week1_pa = 0
            lifts_week2_pa = 0
            lifts_week3_pa = 0
            lifts_week4_pa = 0
            period1 = datetime.datetime.utcnow()-datetime.timedelta(days = 0)
            period2 = datetime.datetime.utcnow()-datetime.timedelta(days = 7)
            period3 = datetime.datetime.utcnow()-datetime.timedelta(days = 14)
            period4 = datetime.datetime.utcnow()-datetime.timedelta(days = 21)
            period5 = datetime.datetime.utcnow()-datetime.timedelta(days = 28)
            #lifts_string = 'Week1 | '

            for lift in user_lifts:
                if lift['driver_id'] == user['_id']:
                    rides_num = rides_num + 1
                    if lift['status'] == 'COMPLETED':
                        rides_completed_num = rides_completed_num + 1
                    elif lift['status'] == 'PENDING':
                        rides_pending_num = rides_pending_num + 1
                    elif lift['status'] == 'ACTIVE':
                        rides_active_num = rides_active_num + 1
                    elif lift['status'] == 'REFUSED':
                        rides_refused_num = rides_refused_num + 1
                    elif lift['status'] == 'CANCELLED':
                        rides_cancelled_num = rides_cancelled_num + 1

                    if  period1 >= lift['_updated'] > period2:
                        lifts_week4_dr = lifts_week4_dr + 1
                    elif period2 >= lift['_updated'] > period3:
                        lifts_week3_dr = lifts_week3_dr + 1
                    elif period3 >= lift['_updated'] > period4:
                        lifts_week2_dr = lifts_week2_dr + 1
                    elif period4 >= lift['_updated'] > period5:
                        lifts_week1_dr = lifts_week1_dr + 1
                if lift['passenger_id'] == user['_id']:
                    lifts_num = lifts_num + 1
                    if lift['status'] == 'COMPLETED':
                        lifts_completed_num = lifts_completed_num + 1
                    elif lift['status'] == 'PENDING':
                        lifts_pending_num = lifts_pending_num + 1
                    elif lift['status'] == 'ACTIVE':
                        lifts_active_num = lifts_active_num + 1
                    elif lift['status'] == 'REFUSED':
                        lifts_refused_num = lifts_refused_num + 1
                    elif lift['status'] == 'CANCELLED':
                        lifts_cancelled_num = lifts_cancelled_num + 1

                    if  period1 >= lift['_updated'] > period2:
                        lifts_week4_pa = lifts_week4_pa + 1
                    elif period2 >= lift['_updated'] > period3:
                        lifts_week3_pa = lifts_week3_pa + 1
                    elif period3 >= lift['_updated'] > period4:
                        lifts_week2_pa = lifts_week2_pa + 1
                    elif period4 >= lift['_updated'] > period5:
                        lifts_week1_pa = lifts_week1_pa + 1

            for ride in user_rides:
                if  period1 >= ride['_updated'] > period2:
                    lifts_week4_dr = lifts_week4_dr + 1
                elif period2 >= ride['_updated'] > period3:
                    lifts_week3_dr = lifts_week3_dr + 1
                elif period3 >= ride['_updated'] > period4:
                    lifts_week2_dr = lifts_week2_dr + 1
                elif period4 >= ride['_updated'] > period5:
                    lifts_week1_dr = lifts_week1_dr + 1
 
            csv_list.append([user['email'], str(lifts_week1_dr), str(lifts_week2_dr), str(lifts_week3_dr), str(lifts_week4_dr), str(lifts_week1_dr + lifts_week2_dr + lifts_week3_dr + lifts_week4_dr), str(lifts_week1_pa), str(lifts_week2_pa), str(lifts_week3_pa), str(lifts_week4_pa), str(lifts_week1_pa + lifts_week2_pa + lifts_week3_pa + lifts_week4_pa), site['name']])
        
    with open('scripts/user_activity.csv', 'w') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        #print('number of rows: ', len(csv_list))
        for row in csv_list:
            filewriter.writerow(row)

#===============================================================================
# user_rating_csv ()
#===============================================================================
def user_rating_csv(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    sites_collection = db[MONGO_SITES_COLLECTION]
    feedbacks_collection = db[MONGO_FEEDBACKS_COLLECTION]
    csv_list = []

    cursor_sites = sites_collection.find({}, { 'bounding_box': 1, 'name': 1 })
    cursor_users = users_collection.find({ 'email': { '$ne': 'driver@rdex.com' } }, { '_id': 1, 'name': 1, 'email': 1 })
    cursor_feedbacks = feedbacks_collection.find({}, { 'rating': 1, 'lift_id': 1, 'reviewed_id': 1, 'role': 1 })

    # store total users
    users = []
    for user in cursor_users:
        users.append(user)

    # store total feedbacks
    feedbacks = []
    for feedback in cursor_feedbacks:
        feedbacks.append(feedback)

    csv_list.append(['User', 'drivers 5-star', 'drivers 4-star', 'drivers 3-star', 'drivers 2-star', 'drivers 1-star', 'Total received by drivers', 'passengers 5-star', 'passengers 4-star', 'passengers 3-star', 'passengers 2-star', 'passengers 1-star', 'Total received by passengers', 'Total', 'Average rating', 'Site'])

    # For every site in db
    for site in cursor_sites:
        
        bb_minlat = site['bounding_box']['min_lat']
        bb_minlon = site['bounding_box']['min_lon']
        bb_maxlat = site['bounding_box']['max_lat']
        bb_maxlon = site['bounding_box']['max_lon']
        lookup1 = { '$and': [ {'end_point.point.lat': {'$gte': bb_minlat}} , \
                            {'end_point.point.lat': {'$lte': bb_maxlat}} , \
                            {'end_point.point.lon': {'$gte': bb_minlon}} , \
                            {'end_point.point.lon': {'$lte': bb_maxlon}} ] }
        lookup2 = { '$and': [ {'start_point.point.lat': {'$gte': bb_minlat}} , \
                            {'start_point.point.lat': {'$lte': bb_maxlat}} , \
                            {'start_point.point.lon': {'$gte': bb_minlon}} , \
                            {'start_point.point.lon': {'$lte': bb_maxlon}} ] }
        lookup_lifts = { '$or': [ lookup1, lookup2 ] }

        cursor_lifts = lifts_collection.find(lookup_lifts, { '_id': 1, 'driver_id' : 1 , 'passenger_id' : 1 })

        # store total lifts
        lifts = []
        for lift in cursor_lifts:
            lifts.append(lift)

        for user in users:
            # store user lifts
            user_lifts = []
            for lift in lifts:
                if lift['driver_id'] == user['_id'] or lift['passenger_id'] == user['_id']:
                    user_lifts.append(lift)

            feedbacks_drivers = 0
            feedbacks_drivers5 = 0
            feedbacks_drivers4 = 0
            feedbacks_drivers3 = 0
            feedbacks_drivers2 = 0
            feedbacks_drivers1 = 0
            feedbacks_passengers = 0
            feedbacks_passengers5 = 0
            feedbacks_passengers4 = 0
            feedbacks_passengers3 = 0
            feedbacks_passengers2 = 0
            feedbacks_passengers1 = 0
            total = 0

            for lift in user_lifts:
                # store driver feedback
                driver_feedback = []
                for feedback in feedbacks:
                    if feedback['lift_id'] == lift['_id'] and feedback['reviewed_id'] == user['_id'] and feedback['role'] == 'driver':
                        driver_feedback.append(feedback)
                if len(driver_feedback) > 0:
                    feedbacks_drivers = feedbacks_drivers + len(driver_feedback)
                    for feedback in driver_feedback:
                        if feedback['rating'] == 5: 
                            feedbacks_drivers5 = feedbacks_drivers5 + 1
                        elif feedback['rating'] == 4: 
                            feedbacks_drivers4 = feedbacks_drivers4 + 1
                        elif feedback['rating'] == 3: 
                            feedbacks_drivers3 = feedbacks_drivers3 + 1
                        elif feedback['rating'] == 2: 
                            feedbacks_drivers2 = feedbacks_drivers2 + 1
                        elif feedback['rating'] == 1: 
                            feedbacks_drivers1 = feedbacks_drivers1 + 1
                        total = total + feedback['rating']
                # store passenger feedback
                passenger_feedback = []
                for feedback in feedbacks:
                    if feedback['lift_id'] == lift['_id'] and feedback['reviewed_id'] == user['_id'] and feedback['role'] == 'passenger':
                        passenger_feedback.append(feedback)
                if len(passenger_feedback) > 0:
                    feedbacks_passengers = feedbacks_passengers + len(passenger_feedback)
                    for feedback in passenger_feedback:
                        if feedback['rating'] == 5: 
                            feedbacks_passengers5 = feedbacks_passengers5 + 1
                        elif feedback['rating'] == 4: 
                            feedbacks_passengers4 = feedbacks_passengers4 + 1
                        elif feedback['rating'] == 3: 
                            feedbacks_passengers3 = feedbacks_passengers3 + 1
                        elif feedback['rating'] == 2: 
                            feedbacks_passengers2 = feedbacks_passengers2 + 1
                        elif feedback['rating'] == 1: 
                            feedbacks_passengers1 = feedbacks_passengers1 + 1
                        total = total + feedback['rating']
            
            if (feedbacks_drivers + feedbacks_passengers > 0):
                csv_list.append([user['email'], str(feedbacks_drivers5), str(feedbacks_drivers4), str(feedbacks_drivers3), str(feedbacks_drivers2), str(feedbacks_drivers1), str(feedbacks_drivers), str(feedbacks_passengers5), str(feedbacks_passengers4), str(feedbacks_passengers3), str(feedbacks_passengers2), str(feedbacks_passengers1), str(feedbacks_passengers), str(feedbacks_drivers + feedbacks_passengers), str((round(total / (feedbacks_drivers + feedbacks_passengers),1))), site['name']])

    with open('scripts/user_rating.csv', 'w') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in csv_list:
            filewriter.writerow(row)

#===============================================================================
# registered_users_csv ()
#===============================================================================
def registered_users_csv(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    sites_collection = db[MONGO_SITES_COLLECTION]
    users_collection = db[MONGO_USERS_COLLECTION]
    csv_list = []
    user_emails = []
    user_names = []

    cursor_sites = sites_collection.find()
    csv_list.append(['Site', 'Name', 'Email'])

    for site in cursor_sites:
        users_list = []
        for email in site['users']:
            if email not in user_emails:
                user = users_collection.find_one({'email': email})
                users_list.append([user['name'], email])
                user_emails.append(email)
                user_names.append(user['name'])
            # If user already found in db
            else:
                x = user_emails.index(email)
                users_list.append([user_names[x],email])
        # Sort list by name
        users_list = sorted(users_list, key=itemgetter(0))
        for user in users_list:
            csv_list.append([site['name'], user[0], user[1]])
    with open('scripts/registered_users.csv', 'w') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in csv_list:
            filewriter.writerow(row)

#===============================================================================
# external_carpooling_csv ()
#===============================================================================
def external_carpooling_csv(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    sites_collection = db[MONGO_SITES_COLLECTION]
    csv_list = []

    cursor_sites = sites_collection.find()
    csv_list.append(['SocialCar user', 'External driver uuid', 'URL', 'Site'])

    for site in cursor_sites:
        for item in site['external_carpooling']:
            csv_list.append([item['username'], item['uuid'], item['url'], site['name']])

    with open('scripts/external_carpooling.csv', 'w') as csvfile:
        filewriter = csv.writer(csvfile, delimiter=',', quotechar='|', quoting=csv.QUOTE_MINIMAL)
        for row in csv_list:
            filewriter.writerow(row)

#===============================================================================
# main ()
#===============================================================================
def main(dbname):
    user_activity_csv(dbname)
    user_rating_csv(dbname)
    registered_users_csv(dbname)
    external_carpooling_csv(dbname)

if __name__ == '__main__':
    main(dbname)