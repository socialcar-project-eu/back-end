import os
import sys
import pymongo
import time, datetime, threading
from socialcar.utils import remove_non_ascii

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
# calculate_user_stats ()
#===============================================================================
def calculate_user_stats(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    rides_collection = db[MONGO_RIDES_COLLECTION]

    cursor_users = users_collection.find({ 'email': {'$regex': '^((?!rdex).)*$'} }, { 'cars': 1, 'social_provider': 1, 'travel_preferences': 1, 'platform': 1 })
    cursor_rides = rides_collection.find({}, { 'driver_id': 1 })

    # store total rides
    rides = []
    for ride in cursor_rides:
        rides.append(ride)

    driver_num = 0
    passenger_num = 0
    android_num = 0
    ios_num = 0
    social_num = 0
    fb_num = 0
    gp_num = 0
    carpool_num = 0
    tracking_num = 0

    for user in cursor_users:
        # store user rides
        user_rides = []
        for ride in rides:
            if ride['driver_id'] == user['_id']:
                user_rides.append(ride)

        # calculate drivers/passengers percentage
        if not user['cars']:
            passenger_num = passenger_num + 1
        else:
            driver_num = driver_num + 1
        # calculate platform percentage
        if 'platform' in user:
            if user['platform'] == 'ANDROID':
                android_num = android_num + 1
            elif user['platform'] == 'IOS':
                ios_num = ios_num + 1
        # calculate socialmedia percentage
        if 'social_provider' in user:
            social_num = social_num + 1
            if user['social_provider']['social_network'] == 'FACEBOOK':
                fb_num = fb_num + 1
            elif user['social_provider']['social_network'] == 'GOOGLE_PLUS':
                gp_num = gp_num + 1
        # calculate carpool percentage
        if len(user_rides) > 0:
            carpool_num = carpool_num + 1
        # calculate_user_tracking_percentage
        if 'travel_preferences' in user:
            if user['travel_preferences']['gps_tracking']:
                tracking_num = tracking_num + 1

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Users<button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv1&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv1">')

    f.write('<div class="panel-group">')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Total users: <b>%s</b></div>' % (cursor_users.count()))
    f.write('<div class="panel-body">')
    f.write('<ul><li>Drivers: %s (%s%%)</li>' % (driver_num, round((driver_num * 100 / cursor_users.count()),0)))
    f.write('<li>Passengers: %s (%s%%)</li></ul>' % (passenger_num, round((passenger_num * 100 / cursor_users.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Platform:</div>')
    f.write('<div class="panel-body">')
    f.write('<ul><li>Android users: %s (%s%%)</li>' % (android_num, round((android_num * 100 / cursor_users.count()),0)))
    f.write('<li>iOS users: %s (%s%%)</li></ul>' % (ios_num, round((ios_num * 100 / cursor_users.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Users importing profiles from social media: <b>%s</b> (%s%%)</div>' % (social_num, round((social_num * 100 / cursor_users.count()),0)))
    f.write('<div class="panel-body">')
    f.write('<ul><li>Facebook users: %s (%s%%)</li>' % (fb_num, round((fb_num * 100 / social_num),0)))
    f.write('<li>Google+ users: %s (%s%%)</li></ul>' % (gp_num, round((gp_num * 100 / social_num),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Drivers offering carpooling (at least once): <b>%s</b> (%s%%)</div>' % (carpool_num, round((carpool_num * 100 / cursor_users.count()),0)))
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Users agreeing to real time tracking: <b>%s</b> (%s%%)</div>' % (tracking_num, round((tracking_num * 100 / cursor_users.count()),0)))
    f.write('</div>')

    f.write('</div>')

    f.write('</div>')
    f.write('</div>')

#===============================================================================
# calculate_registered_users ()
#===============================================================================
def calculate_registered_users(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    sites_collection = db[MONGO_SITES_COLLECTION]
    users_collection = db[MONGO_USERS_COLLECTION]

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Registered Users<button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv8&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv8">')

    cursor_sites = sites_collection.find()

    # For every site in db
    for site in cursor_sites:
        users_list = []
        for email in list(set(site['users'])):
            user = users_collection.find_one({'email': email})
            users_list.append([user['name'], email])
        f.write('<div class="panel panel-default">')
        f.write('<div class="panel-heading">%s <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;%s9&#39;)">Show/Hide</button><div class="clearfix"></div></div>' % (site['name'], site['name']))
        f.write('<table class="table table-hover" id="%s9" style="display: none;"><tr><th>Name</th><th>Email</th></tr>' % (site['name']))
        # For every user in site
        for user in users_list:
            f.write('<tr><td>%s</td>' % (remove_non_ascii(user[0])))
            f.write('<td><span style="font-style: italic; color: blue;">%s</span></td></tr>' % user[1])
        f.write('</table>')
        f.write('</div>')
    f.write('</div>')
    f.write('</div>')
    f.write('<script>function myFunction(toHide) {var x = document.getElementById(toHide);if (x.style.display === "none") {x.style.display = "block";} else {x.style.display = "none";}}</script>')
    f.write('<script>$(document).ready(function(){$(&#34;[data-toggle="tooltip"]&#34;).tooltip();});</script>')

#===============================================================================
# calculate_lifts_per_user ()
#===============================================================================
def calculate_lifts_per_user(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    rides_collection = db[MONGO_RIDES_COLLECTION]
    sites_collection = db[MONGO_SITES_COLLECTION]
    period = datetime.datetime.utcnow()-datetime.timedelta(days=30)

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">User Details<button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv2&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv2">')

    cursor_sites = sites_collection.find({}, { 'bounding_box': 1, 'name': 1 })
    cursor_users = users_collection.find({ 'email': {'$regex': '^((?!rdex).)*$'} }, { '_id': 1, 'name': 1, 'email': 1, 'travel_preferences': 1 })

    # store total users
    users = []
    for user in cursor_users:
        users.append(user)

    # For every site in db
    for site in cursor_sites:
        f.write('<div class="panel panel-default">')
        f.write('<div class="panel-heading">%s <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;%s&#39;)">Show/Hide</button><div class="clearfix"></div></div>' % (site['name'], site['name']))
        f.write('<table class="table table-hover" id="%s" style="display: none;"><tr><th>User</th><th>Tracking</th><th>Lifts offered (driver)</th><th>Lifts requested (passenger)</th><th>Total</th><th>Last Month</th></tr>' % (site['name']))

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
            lifts_string = 'Week1 | '
            gps_tracking = 'Disabled'
            if 'travel_preferences' in user:
                gps_tracking = 'Enabled' if user['travel_preferences']['gps_tracking'] else 'Disabled'

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
 
            total_lifts = lifts_week1_pa + lifts_week2_pa + lifts_week3_pa + lifts_week4_pa + lifts_week1_dr + lifts_week2_dr + lifts_week3_dr + lifts_week4_dr

            lifts_string = 'Total: <b>' + str(total_lifts) + '</b>' + \
                            '<ul><li><a href="#" data-toggle="tooltip" data-placement="right" title="' + str(period5.date().strftime('%d/%m/%y')) + ' - ' + str(period4.date().strftime('%d/%m/%y')) + '">Week1</a>: <b>' + str(lifts_week1_dr + lifts_week1_pa) + '</b> (Offered: ' + str(lifts_week1_dr) + ' | Requested: ' + str(lifts_week1_pa) + ')</li>' + \
                            '<li><a href="#" data-toggle="tooltip" data-placement="right" title="' + str(period4.date().strftime('%d/%m/%y')) + ' - ' + str(period3.date().strftime('%d/%m/%y')) + '">Week2</a>: <b>' + str(lifts_week2_dr + lifts_week2_pa) + '</b> (Offered: ' + str(lifts_week2_dr) + ' | Requested: ' + str(lifts_week2_pa) + ')</li>' + \
                            '<li><a href="#" data-toggle="tooltip" data-placement="right" title="' + str(period3.date().strftime('%d/%m/%y')) + ' - ' + str(period2.date().strftime('%d/%m/%y')) + '">Week3</a>: <b>' + str(lifts_week3_dr + lifts_week3_pa) + '</b> (Offered: ' + str(lifts_week3_dr) + ' | Requested: ' + str(lifts_week3_pa) + ')</li>' + \
                            '<li><a href="#" data-toggle="tooltip" data-placement="right" title="' + str(period2.date().strftime('%d/%m/%y')) + ' - ' + str(period1.date().strftime('%d/%m/%y')) + '">Week4</a>: <b>' + str(lifts_week4_dr + lifts_week4_pa) + '</b> (Offered: ' + str(lifts_week4_dr) + ' | Requested: ' + str(lifts_week4_pa) + ')</li></ul>'
            
            if (rides_num + lifts_num > 0):
                f.write('<tr><td>%s <br><span style="font-style: italic; color: blue;">%s</span></td>' % (remove_non_ascii(user['name']), user['email']))
                f.write('<td>%s' % (gps_tracking))
                f.write('<td>Total: <b>%s</b>' % (rides_num))
                f.write('<ul><li>Completed: <b>%s</b> (%s%%)</li>' % (rides_completed_num, round((rides_completed_num * 100 / rides_num),0))) if (rides_num != 0) else f.write('<ul><li>Completed: <b>0</b> (0%)</li>')
                f.write('<li>Active: <b>%s</b> (%s%%)</li>' % (rides_active_num, round((rides_active_num * 100 / rides_num),0))) if (rides_num != 0) else f.write('<li>Active: <b>0</b> (0%)</li>')
                f.write('<li>Cancelled: <b>%s</b> (%s%%)</li>' % (rides_cancelled_num, round((rides_cancelled_num * 100 / rides_num),0))) if (rides_num != 0) else f.write('<li>Cancelled: <b>0</b> (0%)</li>')
                f.write('<li>Pending: <b>%s</b> (%s%%)</li>' % (rides_pending_num, round((rides_pending_num * 100 / rides_num),0))) if (rides_num != 0) else f.write('<li>Pending: <b>0</b> (0%)</li>')
                f.write('<li>Refused: <b>%s</b> (%s%%)</li></ul>' % (rides_refused_num, round((rides_refused_num * 100 / rides_num),0))) if (rides_num != 0) else f.write('<li>Refused: <b>0</b> (0%)</li></ul>')
                f.write('<td>Total: <b>%s</b>' % (lifts_num))
                f.write('<ul><li>Completed: <b>%s</b> (%s%%)</li>' % (lifts_completed_num, round((lifts_completed_num * 100 / lifts_num),0))) if (lifts_num != 0) else f.write('<ul><li>Completed: <b>0</b> (0%)</li>')
                f.write('<li>Active: <b>%s</b> (%s%%)</li>' % (lifts_active_num, round((lifts_active_num * 100 / lifts_num),0))) if (lifts_num != 0) else f.write('<li>Active: <b>0</b> (0%)</li>')
                f.write('<li>Cancelled: <b>%s</b> (%s%%)</li>' % (lifts_cancelled_num, round((lifts_cancelled_num * 100 / lifts_num),0))) if (lifts_num != 0) else f.write('<li>Cancelled: <b>0</b> (0%)</li>')
                f.write('<li>Pending: <b>%s</b> (%s%%)</li>' % (lifts_pending_num, round((lifts_pending_num * 100 / lifts_num),0))) if (lifts_num != 0) else f.write('<li>Pending: <b>0</b> (0%)</li>')
                f.write('<li>Refused: <b>%s</b> (%s%%)</li></ul></td>' % (lifts_refused_num, round((lifts_refused_num * 100 / lifts_num),0))) if (lifts_num != 0) else f.write('<li>Refused: <b>0</b> (0%)</li></ul></td>')
                f.write('<td><b>%s</b></td>' % (rides_num + lifts_num))
                f.write('<td>%s</td></tr>' % (lifts_string))
        f.write('</table>')
        f.write('</div>')
    f.write('</div>')
    f.write('</div>')
    f.write('<script>function myFunction(toHide) {var x = document.getElementById(toHide);if (x.style.display === "none") {x.style.display = "block";} else {x.style.display = "none";}}</script>')
    f.write('<script>$(document).ready(function(){$(&#34;[data-toggle="tooltip"]&#34;).tooltip();});</script>')

#===============================================================================
# calculate_time_of_rides ()
#===============================================================================
def calculate_time_of_rides(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    rides_collection = db[MONGO_RIDES_COLLECTION]

    cursor_rides = rides_collection.find({}, { 'date': 1, 'extras': 1 })

    internal_rides_num = 0
    external_rides_num = 0
    early_morning_num = 0
    early_morning_00_02 = 0
    early_morning_02_04 = 0
    early_morning_04_06 = 0
    morning_num = 0
    morning_06_08 = 0
    morning_08_10 = 0
    morning_10_12 = 0
    afternoon_num = 0
    afternoon_12_14 = 0
    afternoon_14_16 = 0
    afternoon_16_18 = 0
    evening_num = 0
    evening_18_20 = 0
    evening_20_22 = 0
    evening_22_24 = 0

    for ride in cursor_rides:
        if 'extras' in ride:
            external_rides_num = external_rides_num + 1
        else:
            internal_rides_num = internal_rides_num + 1
        ride_hour = datetime.datetime.fromtimestamp(ride['date']).hour
        if ride_hour < 6:
            early_morning_num = early_morning_num + 1
            if 0 <= ride_hour < 2:
                early_morning_00_02 = early_morning_00_02 + 1
            if 2 <= ride_hour < 4:
                early_morning_02_04 = early_morning_02_04 + 1
            if 4 <= ride_hour < 6:
                early_morning_04_06 = early_morning_04_06 + 1
        elif ride_hour < 12:
            morning_num = morning_num + 1
            if 6 <= ride_hour < 8:
                morning_06_08 = morning_06_08 + 1
            if 8 <= ride_hour < 10:
                morning_08_10 = morning_08_10 + 1
            if 10 <= ride_hour < 12:
                morning_10_12 = morning_10_12 + 1
        elif ride_hour < 18:
            afternoon_num = afternoon_num + 1
            if 12 <= ride_hour < 14:
                afternoon_12_14 = afternoon_12_14 + 1
            if 14 <= ride_hour < 16:
                afternoon_14_16 = afternoon_14_16 + 1
            if 16 <= ride_hour < 18:
                afternoon_16_18 = afternoon_16_18 + 1
        else:
            evening_num = evening_num + 1
            if 18 <= ride_hour < 20:
                evening_18_20 = evening_18_20 + 1
            if 20 <= ride_hour < 22:
                evening_20_22 = evening_20_22 + 1
            if 22 <= ride_hour < 24:
                evening_22_24 = evening_22_24 + 1

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Rides in DB <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv3&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv3">')

    f.write('<div class="panel-group">')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Total rides: <b>%s</b></div>' % (cursor_rides.count()))
    f.write('<div class="panel-body">')
    f.write('<ul><li>Internal rides: %s (%s%%)</li>' % (internal_rides_num, round((internal_rides_num * 100 / cursor_rides.count()),0)))
    f.write('<li>External rides: %s (%s%%)</li>' % (external_rides_num, round((external_rides_num * 100 / cursor_rides.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Rides offered in the early morning (00:00 - 06:00): <b>%s</b> (%s%%)</div>' % (early_morning_num, round((early_morning_num * 100 / cursor_rides.count()),0)))
    f.write('<div class="panel-body">')
    f.write('<ul><li>00:00 - 02:00: %s (%s%%)</li>' % (early_morning_00_02, round((early_morning_00_02 * 100 / cursor_rides.count()),0)))
    f.write('<li>02:00 - 04:00: %s (%s%%)</li>' % (early_morning_02_04, round((early_morning_02_04 * 100 / cursor_rides.count()),0)))
    f.write('<li>04:00 - 06:00: %s (%s%%)</li></ul>' % (early_morning_04_06, round((early_morning_04_06 * 100 / cursor_rides.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Rides offered in the morning (06:00 - 12:00): <b>%s</b> (%s%%)</div>' % (morning_num, round((morning_num * 100 / cursor_rides.count()),0)))
    f.write('<div class="panel-body">')
    f.write('<ul><li>06:00 - 08:00: %s (%s%%)</li>' % (morning_06_08, round((morning_06_08 * 100 / cursor_rides.count()),0)))
    f.write('<li>08:00 - 10:00: %s (%s%%)</li>' % (morning_08_10, round((morning_08_10 * 100 / cursor_rides.count()),0)))
    f.write('<li>10:00 - 12:00: %s (%s%%)</li></ul>' % (morning_10_12, round((morning_10_12 * 100 / cursor_rides.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Rides offered in the afternoon (12:00 - 18:00): <b>%s</b> (%s%%)</div>' % (afternoon_num, round((afternoon_num * 100 / cursor_rides.count()),0)))
    f.write('<div class="panel-body">')
    f.write('<ul><li>12:00 - 14:00: %s (%s%%)</li>' % (afternoon_12_14, round((afternoon_12_14 * 100 / cursor_rides.count()),0)))
    f.write('<li>14:00 - 16:00: %s (%s%%)</li>' % (afternoon_14_16, round((afternoon_14_16 * 100 / cursor_rides.count()),0)))
    f.write('<li>16:00 - 18:00: %s (%s%%)</li></ul>' % (afternoon_16_18, round((afternoon_16_18 * 100 / cursor_rides.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Rides offered in the evening (18:00 - 00:00): <b>%s</b> (%s%%)</div>' % (evening_num, round((evening_num * 100 / cursor_rides.count()),0)))
    f.write('<div class="panel-body">')
    f.write('<ul><li>18:00 - 20:00: %s (%s%%)</li>' % (evening_18_20, round((evening_18_20 * 100 / cursor_rides.count()),0)))
    f.write('<li>20:00 - 22:00: %s (%s%%)</li>' % (evening_20_22, round((evening_20_22 * 100 / cursor_rides.count()),0)))
    f.write('<li>22:00 - 00:00: %s (%s%%)</li></ul>' % (evening_22_24, round((evening_22_24 * 100 / cursor_rides.count()),0)))
    f.write('</div>')
    f.write('</div>')

    f.write('</div>')

    f.write('</div>')
    f.write('</div>')

#===============================================================================
# calculate_rides_in_solutions ()
#===============================================================================
def calculate_rides_in_solutions(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    sites_collection = db[MONGO_SITES_COLLECTION]

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Rides in Solutions (data since 16-10-2017)<button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv6&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv6">')

    cursor_sites = sites_collection.find({}, { 'bounding_box': 1, 'name': 1, 'ride_details': 1 })

    # For every site in db
    for site in cursor_sites:
        rides_sum = site['ride_details']['internal'] + site['ride_details']['external']
        internal_rides_num = site['ride_details']['internal']
        external_rides_num = site['ride_details']['external']
        carpooling_only_num = site['ride_details']['carpooling_only']
        carpooling_PT_num = site['ride_details']['carpooling_PT']
        total_solutions_num = site['ride_details']['total_solutions']

        f.write('<div class="panel panel-default">')
        f.write('<div class="panel-heading">%s <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;%s3&#39;)">Show/Hide</button><div class="clearfix"></div></div>' % (site['name'], site['name']))
        f.write('<div class="panel-body" id="%s3" style="display: none;">' % (site['name']))
        f.write('<ul><li>Total solutions: <b>%s</b></li>' % (total_solutions_num))
        f.write('<li>Internal Rides: <b>%s</b> (%s%%)</li>' % (internal_rides_num, round((internal_rides_num * 100 / rides_sum),0))) if (rides_sum != 0) else f.write('<li>Internal Rides: <b>0</b> (0%)</li>')
        f.write('<li>External Rides: <b>%s</b> (%s%%)</li>' % (external_rides_num, round((external_rides_num * 100 / rides_sum),0))) if (rides_sum != 0) else f.write('<li>External Rides: <b>0</b> (0%)</li>')
        f.write('<li>Carpooling only Rides: <b>%s</b> (%s%%)</li>' % (carpooling_only_num, round((carpooling_only_num * 100 / rides_sum),0))) if (rides_sum != 0) else f.write('<li>Carpooling only Rides: <b>0</b> (0%)</li>')
        f.write('<li>Carpooling + PT Rides: <b>%s</b> (%s%%)</li></ul>' % (carpooling_PT_num, round((carpooling_PT_num * 100 / rides_sum),0))) if (rides_sum != 0) else f.write('<li>Carpooling + PT Rides: <b>0</b> (0%)</li>')
        f.write('</div>')
        f.write('</div>')

    f.write('</div>')
    f.write('</div>')
    f.write('<script>function myFunction(toHide) {var x = document.getElementById(toHide);if (x.style.display === "none") {x.style.display = "block";} else {x.style.display = "none";}}</script>')
    f.write('<script>$(document).ready(function(){$(&#34;[data-toggle="tooltip"]&#34;).tooltip();});</script>')

#===============================================================================
# calculate_feedbacks_percentage ()
#===============================================================================
def calculate_feedbacks_percentage(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    feedbacks_collection = db[MONGO_FEEDBACKS_COLLECTION]

    cursor_lifts = lifts_collection.find({}, { '_id': 1 })

    feedbacks_num = 0
    feedbacks_driver_num = 0
    feedbacks_passenger_num = 0
    ratings_5_dr = 0
    ratings_4_dr = 0
    ratings_3_dr = 0
    ratings_2_dr = 0
    ratings_1_dr = 0
    ratings_5_pa = 0
    ratings_4_pa = 0
    ratings_3_pa = 0
    ratings_2_pa = 0
    ratings_1_pa = 0

    for lift in cursor_lifts:
        cursor_feedback = feedbacks_collection.find({'lift_id':lift['_id']}, { 'role': 1 })
        if cursor_feedback.count() > 0:
            feedbacks_num = feedbacks_num + 1
            for feedback in cursor_feedback:
                if feedback['role'] == 'passenger':
                    feedbacks_passenger_num = feedbacks_passenger_num + 1
                else:
                    feedbacks_driver_num = feedbacks_driver_num + 1
    cursor_feedbacks = feedbacks_collection.find({}, { 'role': 1, 'rating': 1 })
    for feedback in cursor_feedbacks:
        if feedback['role'] == 'driver':
            if feedback['rating'] == 5: 
                ratings_5_dr = ratings_5_dr + 1
            elif feedback['rating'] == 4: 
                ratings_4_dr = ratings_4_dr + 1
            elif feedback['rating'] == 3: 
                ratings_3_dr = ratings_3_dr + 1
            elif feedback['rating'] == 2: 
                ratings_2_dr = ratings_2_dr + 1
            elif feedback['rating'] == 1: 
                ratings_1_dr = ratings_1_dr + 1
    cursor_feedbacks = feedbacks_collection.find({}, { 'role': 1, 'rating': 1 })
    for feedback in cursor_feedbacks:
        if feedback['role'] == 'passenger':
            if feedback['rating'] == 5: 
                ratings_5_pa = ratings_5_pa + 1
            elif feedback['rating'] == 4: 
                ratings_4_pa = ratings_4_pa + 1
            elif feedback['rating'] == 3: 
                ratings_3_pa = ratings_3_pa + 1
            elif feedback['rating'] == 2: 
                ratings_2_pa = ratings_2_pa + 1
            elif feedback['rating'] == 1: 
                ratings_1_pa = ratings_1_pa + 1

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Feedback <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv4&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv4">')

    f.write('<div class="panel-group">')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Rides with user feedback: <b>%s</b> (%s%%)</div>' % (feedbacks_num, round((feedbacks_num * 100 / cursor_lifts.count()),0))) if (cursor_lifts.count() != 0) else f.write('<div class="panel-heading">Rides with user feedback: <b>0</b> (0%)</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Feedback sent by drivers: <b>%s</b> (%s%%)</div>' % (feedbacks_driver_num, round((feedbacks_driver_num * 100 / cursor_feedbacks.count()),0)))  if (cursor_feedbacks.count() != 0) else f.write('<div class="panel-heading">Feedback sent by drivers: <b>0</b> (0%)</div>')
    f.write('<div class="panel-body">')
    f.write('<div>Ratings:</div>')
    f.write('<ul><li>5-stars: %s</li>' % (ratings_5_dr))
    f.write('<li>4-stars: %s</li>' % (ratings_4_dr))
    f.write('<li>3-stars: %s</li>' % (ratings_3_dr))
    f.write('<li>2-stars: %s</li>' % (ratings_2_dr))
    f.write('<li>1-stars: %s</li></ul>' % (ratings_1_dr))
    f.write('<div>Reviews:</div>')
    f.write('<ul>')
    cursor_feedbacks = feedbacks_collection.find({}, { 'review': 1, 'role': 1 })
    for feedback in cursor_feedbacks:
        if feedback['review'] != '' and feedback['role'] == 'driver':
            f.write('<li>%s</li>' % (feedback['review']))
    f.write('</ul>')
    f.write('</div>')
    f.write('</div>')

    f.write('<div class="panel panel-default">')
    f.write('<div class="panel-heading">Feedback sent by passengers: <b>%s</b> (%s%%)</div>' % (feedbacks_passenger_num, round((feedbacks_passenger_num * 100 / cursor_feedbacks.count()),0))) if (cursor_feedbacks.count() != 0) else f.write('<div class="panel-heading">Feedback sent by passengers: <b>0</b> (0%)</div>')
    f.write('<div class="panel-body">')
    f.write('<div>Ratings:</div>')
    f.write('<ul><li>5-stars: %s</li>' % (ratings_5_pa))
    f.write('<li>4-stars: %s</li>' % (ratings_4_pa))
    f.write('<li>3-stars: %s</li>' % (ratings_3_pa))
    f.write('<li>2-stars: %s</li>' % (ratings_2_pa))
    f.write('<li>1-stars: %s</li></ul>' % (ratings_1_pa))
    f.write('<div>Reviews:</div>')
    f.write('<ul>')
    cursor_feedbacks = feedbacks_collection.find({}, { 'review': 1, 'role': 1 })
    for feedback in cursor_feedbacks:
        if feedback['review'] != '' and feedback['role'] == 'passenger':
            f.write('<li>%s</li>' % (feedback['review']))
    f.write('</ul>')
    f.write('</div>')
    f.write('</div>')

    f.write('</div>')

    f.write('</div>')
    f.write('</div>')

#===============================================================================
# calculate_feedback_per_user ()
#===============================================================================
def calculate_feedback_per_user(dbname):
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    users_collection = db[MONGO_USERS_COLLECTION]
    lifts_collection = db[MONGO_LIFTS_COLLECTION]
    sites_collection = db[MONGO_SITES_COLLECTION]
    feedbacks_collection = db[MONGO_FEEDBACKS_COLLECTION]

    f.write('<div class="panel panel-primary">')
    f.write('<div class="panel-heading">Feedback Details<button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;myDiv5&#39;)">Show/Hide All</button><div class="clearfix"></div></div>')
    f.write('<div class="panel-body" style="display: none;" id="myDiv5">')

    cursor_sites = sites_collection.find({}, { 'bounding_box': 1, 'name': 1 })
    cursor_users = users_collection.find({ 'email': {'$regex': '^((?!rdex).)*$'} }, { '_id': 1, 'name': 1, 'email': 1 })
    cursor_feedbacks = feedbacks_collection.find({}, { 'rating': 1, 'lift_id': 1, 'reviewed_id': 1, 'role': 1 })

    # store total users
    users = []
    for user in cursor_users:
        users.append(user)

    # store total feedbacks
    feedbacks = []
    for feedback in cursor_feedbacks:
        feedbacks.append(feedback)

    # For every site in db
    for site in cursor_sites:
        f.write('<div class="panel panel-default">')
        f.write('<div class="panel-heading">%s <button type="button" class="btn btn-default pull-right" onclick="myFunction(&#39;%s2&#39;)">Show/Hide</button><div class="clearfix"></div></div>' % (site['name'], site['name']))
        f.write('<table class="table" id="%s2" style="display: none;"><tr><th>User</th><th>Rating received by drivers</th><th>Rating received by passengers</th><th>Total</th><th>Average Rating</th></tr>' % (site['name']))

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
                f.write('<tr><td>%s <span style="font-style: italic; color: blue;">%s</span></td>' % (remove_non_ascii(user['name']), user['email']))
                f.write('<td>Total: <b>%s</b>' % (feedbacks_drivers))
                f.write('<ul><li>5-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_drivers5, round((feedbacks_drivers5 * 100 / feedbacks_drivers),0))) if (feedbacks_drivers != 0) else f.write('<ul><li>5-stars: <b>0</b> (0%)</li>')
                f.write('<li>4-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_drivers4, round((feedbacks_drivers4 * 100 / feedbacks_drivers),0))) if (feedbacks_drivers != 0) else f.write('<li>4-stars: <b>0</b> (0%)</li>')
                f.write('<li>3-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_drivers3, round((feedbacks_drivers3 * 100 / feedbacks_drivers),0))) if (feedbacks_drivers != 0) else f.write('<li>3-stars: <b>0</b> (0%)</li>')
                f.write('<li>2-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_drivers2, round((feedbacks_drivers2 * 100 / feedbacks_drivers),0))) if (feedbacks_drivers != 0) else f.write('<li>2-stars: <b>0</b> (0%)</li>')
                f.write('<li>1-stars: <b>%s</b> (%s%%)</li></ul>' % (feedbacks_drivers1, round((feedbacks_drivers1 * 100 / feedbacks_drivers),0))) if (feedbacks_drivers != 0) else f.write('<li>1-stars: <b>0</b> (0%)</li></ul>')
                f.write('<td>Total: <b>%s</b>' % (feedbacks_passengers))
                f.write('<ul><li>5-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_passengers5, round((feedbacks_passengers5 * 100 / feedbacks_passengers),0))) if (feedbacks_passengers != 0) else f.write('<ul><li>5-stars: <b>0</b> (0%)</li>')
                f.write('<li>4-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_passengers4, round((feedbacks_passengers4 * 100 / feedbacks_passengers),0))) if (feedbacks_passengers != 0) else f.write('<li>4-stars: <b>0</b> (0%)</li>')
                f.write('<li>3-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_passengers3, round((feedbacks_passengers3 * 100 / feedbacks_passengers),0))) if (feedbacks_passengers != 0) else f.write('<li>3-stars: <b>0</b> (0%)</li>')
                f.write('<li>2-stars: <b>%s</b> (%s%%)</li>' % (feedbacks_passengers2, round((feedbacks_passengers2 * 100 / feedbacks_passengers),0))) if (feedbacks_passengers != 0) else f.write('<li>2-stars: <b>0</b> (0%)</li>')
                f.write('<li>1-stars: <b>%s</b> (%s%%)</li></ul>' % (feedbacks_passengers1, round((feedbacks_passengers1 * 100 / feedbacks_passengers),0))) if (feedbacks_passengers != 0) else f.write('<li>1-stars: <b>0</b> (0%)</li></ul>')
                f.write('<td><b>%s</b></td>' % (feedbacks_drivers + feedbacks_passengers))
                f.write('<td><b>%s</b></td></tr>' % (round(total / (feedbacks_drivers + feedbacks_passengers),1)))
        f.write('</table>')
        f.write('</div>')
    f.write('</div>')
    f.write('</div>')
    f.write('<script>function myFunction(toHide) {var x = document.getElementById(toHide);if (x.style.display === "none") {x.style.display = "block";} else {x.style.display = "none";}}</script>')

#===============================================================================
# write_file_opening ()
#===============================================================================
def write_file_opening():
    f.write('<!DOCTYPE html><html><head><link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.7/css/bootstrap.min.css" integrity="sha384-BVYiiSIFeK1dGmJRAkycuHAHRg32OmUcww7on3RYdg4Va+PmSTsz/K68vbdEjh4u" crossorigin="anonymous"><title>SocialCar Statistics</title></head>')
    f.write('<body><div class="container"><h1 style="color: rgb(150,20,92); text-align: center;">SocialCar Statistics</h1>')
    f.write('<div class="alert alert-warning" role="alert" style="text-align: center;">Generated in %s</div>' % (datetime.datetime.utcnow().strftime('%d-%m-%Y @ %H:%M:%S (UTC)')))

#===============================================================================
# write_file_opening ()
#===============================================================================
def write_file_closing():
    f.write('</div></div></body></html>')

#===============================================================================
# main ()
#===============================================================================
def main(dbname):
    global f
    start_time = time.time()
    f = open('scripts/statistics.html', 'w+')
    write_file_opening()
    calculate_user_stats(dbname)
    calculate_registered_users(dbname)
    calculate_lifts_per_user(dbname)
    calculate_time_of_rides(dbname)
    calculate_rides_in_solutions(dbname)
    calculate_feedbacks_percentage(dbname)
    calculate_feedback_per_user(dbname)
    write_file_closing()
    f.close()

if __name__ == '__main__':
    main(dbname)