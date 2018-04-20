# -*- coding: utf-8 -*-

import os
import re
import time
import json
from collections import defaultdict
import logging
import logging.handlers
import subprocess
import requests
import random
import raven
import bisect
import random
import threading
from scripts.Statistics import STATISTICS_SCRIPT_FOLDER
from scripts.Statistics import main as statistics_main
from scripts.Statistics_csv import main as statisticsCSV_main
from eve import Eve
from eve.auth import BasicAuth, requires_auth
from eve.utils import document_etag
from eve_docs import eve_docs
from eve.methods.post import post_internal
from flask import abort, request, make_response, send_from_directory, Response, copy_current_request_context
from flask_cors import CORS
from flask_bootstrap import Bootstrap
from functools import wraps
from werkzeug.datastructures import ImmutableMultiDict
from socialcar.settings import URL_PREFIX, API_VERSION, USE_SENTRY, SENTRY_DSN, \
                               DEBUG, FCM_HOST, FCM_PORT, FCM_API_KEY, MONGO_DBNAME
from socialcar.randomgen import random_trips
from socialcar.utils import str_to_json, json_to_str, remove_fields, recursively_remove_fields, \
                            objectids_to_strings, str_to_oid, oid_to_str, apply_function, \
                            km2rad, rad2km, timestamp_to_datetime, inside_bounding_box, \
                            remove_non_ascii, find_site_for_rides, waypoints_to_polyline, \
                            haversine_formula, downsample_polyline
from socialcar.fares import rail_fare, bus_fare, carpooling_fare, metro_fare, tram_fare
from scripts.gtfs import route_type_to_text as EXTENDED_TRAVEL_MODES
if USE_SENTRY:
    from raven.handlers.logging import SentryHandler
    from raven.conf import setup_logging

LOG_EVERY_REQ_AND_RES = True

OWNER_FIELD = '_owner'  # Authorization: users can modify only objects they own

OCC_FIELD = '_occ'  # Optimistic Concurrency Control

CUSTOM_ENDPOINTS = [ 'trips', 'rides_boundary', 'rides_internal', 'sites_boundary', 'reports_boundary', 'reports_around', 'stops', 'waiting_time', 'positions_button'  ]

REQUIRED_PARAMS = {
    'trips': [ 'start_lat', 'start_lon', 'end_lat', 'end_lon',
               'start_date', 'end_date', 'use_bus', 'use_metro',
               'use_train', 'transfer_mode' ],
    'stops': [ 'lat', 'lon' ],
    'rides_boundary': [ 'min_lat', 'min_lon', 'max_lat', 'max_lon', 'site' ],
    'sites_boundary': [ 'min_lat', 'min_lon', 'max_lat', 'max_lon' ],
    'reports_boundary': [ 'min_lat', 'min_lon', 'max_lat', 'max_lon' ],
    'reports_around': [ 'lat', 'lon' ],
    'positions_button': [ 'lat', 'lon', 'lift_id' ],
}

STOPS_AROUND_RADIUS_KM = 0.5
REPORTS_AROUND_RADIUS_KM = 0.5
MEAN_VELOCITY = 40
RADIUS = 5

ALLOWED_TRAVEL_MODES = [ 'FEET', 'CAR_POOLING', 'METRO', 'BUS', 'RAIL', 'TRAM' ]

EVE_EXTRA_FIELDS = [ '_created', '_updated', '_etag', '_links', '_deleted',
                     '_version', '_latest_version', '_status', OWNER_FIELD,
                     OCC_FIELD ]

GET_VALUES_SEPARATOR = ','

RESOURCE_SEARCH_FIELDS = {
    'users': [ 'email', 'social_provider.social_id', 'social_provider.social_network' ],
    'rides': [ 'driver_id' ],
    'lifts': [ 'driver_id', 'passenger_id' ],
    'feedbacks': [ 'role', 'reviewer_id', 'reviewed_id', 'date_$gt', 'lift_id' ],
    'positions': [ 'user_id', 'timestamp_$gt', 'timestamp_$lt' ],
    'destinations': [ 'user_id' ],
    'sites': [ 'name' ],
    'messages': [ 'sender_id', 'receiver_id', 'lift_id' ],
}

RESOURCE_GROUP_BY_FIELDS = {
    'positions': [ 'user_id' ],
}

AUTO_EMBED_FIELDS = {
    # These fields must have 'embeddable' = True in settings.py
    'rides': [ 'lifts' ]
}

# Resources that must not be modified by users
PROTECTED_RESOURCES = [ 'reputations' ]

# Urls for which authentication is not needed. Unauthenticated access is only
# allowed on specified resources, using the specified method, and iff the url
# contains the specified params.
# E.g. GET /users?social_provider.social_id=x&social_provider.social_network=y
# doesn't need auth, but GET /users or GET /users?email=a@mail.com needs auth.
# Note: client still needs to send a dummy auth header, e.g. with any user/pass
AUTH_FREE_URLS = {
    'users': {
        'GET': [
            'social_provider.social_id',
            'social_provider.social_network'
        ],
    },
}

EXCLUDE_FROM_LOGS = [ 'route_plan', 'admin' ]

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))

#===============================================================================
# flatten_data ()
#===============================================================================
def flatten_data(data):
    return data['_items'] if '_items' in data else data

#===============================================================================
# actual_resource ()
#===============================================================================
def actual_resource(request):
    # There are some cases where the 'resource' argument passed on function from
    # Eve may not be the actual resource. E.g., it can be None or the value set
    # in 'DOMAIN' on settings.py.
    url = request.base_url
    try:
        _, resource_path = re.split('%s/%s/' % (URL_PREFIX, API_VERSION), url)
        return re.findall(r"[\w']+", resource_path)[0]
    except (ValueError, IndexError):
        return None

#===============================================================================
# response_set_error ()
#===============================================================================
def response_set_error(response, status_code, msg):
    assert not 200 <= status_code < 300
    response.status_code = status_code
    data = '{"_error": {"code": %d, "message": "%s"}}' % (status_code, msg)
    response.set_data(data)

#===============================================================================
# add_object_owner ()
#===============================================================================
def add_object_owner(resource, items, original=None):
    for item in items:
        if resource in PROTECTED_RESOURCES:
            # Since the owner of these objects is a non-existing user, no user
            # can modify these objects and thus only admins can modify them.
            # Onwer must not be a valid email, so no user can be created with
            # this email (and thus have the ability to modify this resource).
            item[OWNER_FIELD] = [ 'NON_EXISTING_USER' ]
        elif resource == 'users' and request.method == 'POST':
            # This request doesn't have auth headers
            item[OWNER_FIELD] = [ item['email'] ]
        elif request.authorization:
            item[OWNER_FIELD] = [ request.authorization['username'] ]
            # In case of lifts, add also the driver as object owner so [s]he
            # can also modify the object, e.g. change its status.
            # If item contains the driver_id (e.g. this a POST or PUT), get
            # driver_id from item. Else (PATCH) get it from existing item in db
            if resource == 'lifts':
                item[OWNER_FIELD] = []
                for owner_field in 'passenger_id', 'driver_id':
                    if owner_field in item:
                        owner_id = item[owner_field]
                    else:
                        assert original and owner_field in original
                        owner_id = original[owner_field]
                    lookup = {'_id': owner_id}
                    user = app.data.driver.db['users'].find_one(lookup)
                    item[OWNER_FIELD].append(user['email'])
        else:
            app.logger.info('Non authorized POST on resource %s' % (resource))

#===============================================================================
# add_occ_field ()
#===============================================================================
def add_occ_field(items):
    for item in items if isinstance(items, list) else [ items ]:
        item[OCC_FIELD] = document_etag(item)

#===============================================================================
# before_insert ()
#===============================================================================
def before_insert(resource, items):
    add_object_owner(resource, items)
    add_occ_field(items)

#===============================================================================
# before_update ()
#===============================================================================
def before_update(resource, updates, original):
    add_object_owner(resource, [ updates ], original)
    add_occ_field(updates)

#===============================================================================
# before_replace ()
#===============================================================================
def before_replace(resource, item, original):
    add_object_owner(resource, [ item ], original)
    add_occ_field(item)

#===============================================================================
# before_delete ()
#===============================================================================
def before_delete(resource, item):
    add_object_owner(resource, [ item ])
    add_occ_field(item)

#===============================================================================
# update_referenced_items ()
#===============================================================================
def update_referenced_items(new_items, reference_id, reference_resource,
                            reference_field, update_func):
    # For each new item, find the item it references and update it
    collection = app.data.driver.db[reference_resource]
    for new_item in new_items if isinstance(new_items, list) else [ new_items ]:
        #-----------------------------------------------------------------------
        # Atomically update item using Optimistic Concurrency Control
        #-----------------------------------------------------------------------
        # If update failed (nModified == 0) the object was modified from
        # another thread between the find() and the update() =>  we must retry
        # the update. Else everythin is ok, break.
        #-----------------------------------------------------------------------
        while True:
            # Find referenced item
            lookup = {reference_field: new_item[reference_id]}
            referenced_item = collection.find_one(lookup)
            old_occ = referenced_item[OCC_FIELD] if referenced_item else None
            # Update referenced item
            referenced_item = update_func(referenced_item, new_item)
            add_occ_field(referenced_item)
            # Write updated item back to db
            if '_id' not in referenced_item:  # new item
                collection.insert(referenced_item)
                break
            else:
                assert old_occ
                lookup.update({OCC_FIELD: old_occ})
                res = collection.update(lookup, referenced_item, upsert = False)
                if res['nModified'] == 1:
                    break

#===============================================================================
# after_insert_users ()
#===============================================================================
def after_insert_users(users):
    for user in users if isinstance(users, list) else [ users ]:
        payload = {
            'user_id': user['_id'],
            'last_update': int(time.time()),
        }
        post_internal('reputations', payload)

#===============================================================================
# after_insert_cars ()
#===============================================================================
def after_insert_cars(cars):
    def update_func(user, car):
        user['cars'].append(car['_id'])
        return user
    update_referenced_items(cars, 'owner_id', 'users', '_id', update_func)

#===============================================================================
# after_delete_car ()
#===============================================================================
def after_delete_car(car):
    def update_func(user, car):
        user['cars'].remove(car['_id'])
        return user
    update_referenced_items(car, 'owner_id', 'users', '_id', update_func)
  
#===============================================================================
# after_insert_rides ()
#===============================================================================
def after_insert_rides(rides):
    for ride in rides if isinstance(rides, list) else [ rides ]:
        update_sites_carpool_info(ride)

#===============================================================================
# after_replace_ride ()
#===============================================================================
def after_replace_ride(updates, ride):
    update_sites_carpool_info(ride)

#===============================================================================
# after_update_ride ()
#===============================================================================
def after_update_ride(updates, ride):
    update_sites_carpool_info(ride)

#===============================================================================
# after_delete_ride ()
#===============================================================================
def after_delete_ride(ride):
    update_sites_carpool_info(ride)

#===============================================================================
# after_insert_lifts ()
#===============================================================================
def after_insert_lifts(lifts):
    def update_func(ride, lift):
        ride['lifts'].append(lift['_id'])
        return ride
    update_referenced_items(lifts, 'ride_id', 'rides', '_id', update_func)

    # Send push notifications to driver for lift request
    for lift in lifts:
        post_process_data('lifts', request, lift)
        notification_thread_lift(lift['driver_id'], lift)

        payload = {
            'lift_id': lift['_id'],
        }
        post_internal('eta_notify', payload)

#===============================================================================
# after_replaced_lift ()
#===============================================================================
def after_replaced_lift(lift, original):
    after_updated_lift(lift, original)

#===============================================================================
# after_updated_lift ()
#===============================================================================
def after_updated_lift(updates, original):
    # 'updates' may contain only the fields to be updated, or the whole
    # updated object (when called from after_replaced_lift())
    lift = original
    lift.update(updates)
    post_process_data('lifts', request, lift)
        
    username = request.authorization['username']
    user = app.data.driver.db['users'].find_one({'email': username})
    assert user and user['email'] == username
    updater = oid_to_str(user['_id'])

    # If the passenger updated the lift, notify the driver (and vice versa)
    if updater == lift['passenger_id']:
        user_to_notify = lift['driver_id']
    else:
        assert updater == lift['driver_id']
        user_to_notify = lift['passenger_id']    
    notification_thread_lift(user_to_notify, lift)
    
#===============================================================================
# after_delete_lift ()
#===============================================================================
def after_delete_lift(lift):
    def update_func(ride, lift):
        ride['lifts'].remove(lift['_id'])
        return ride
    update_referenced_items(lift, 'ride_id', 'rides', '_id', update_func)

#===============================================================================
# after_insert_user_pictures ()
#===============================================================================
def after_insert_user_pictures(pictures):
    def update_func(user, picture):
        # Replace previous picture with new one
        if user['pictures'] != []:
            assert len(user['pictures']) == 1
            pic_collection = app.data.driver.db['user_pictures']
            pic_collection.delete_one({'_id': user['pictures'][0]['_id']})
        user['pictures'] = [{
            '_id': picture['_id'],
            'file': picture['file'],
        }]
        return user
    update_referenced_items(pictures, 'user_id', 'users', '_id', update_func)

#===============================================================================
# after_delete_user_picture ()
#===============================================================================
def after_delete_user_picture(picture):
    def update_func(user, picture):
        user['pictures'] = [ p for p in user['pictures'] if p['_id'] != picture['_id'] ]
        return user
    update_referenced_items(picture, 'user_id', 'users', '_id', update_func)

#===============================================================================
# after_insert_car_pictures ()
#===============================================================================
def after_insert_car_pictures(pictures):
    def update_func(car, picture):
        car['pictures'] = car['pictures'] + [{
            '_id': picture['_id'],
            'file': picture['file'],
        }]
        return car
    update_referenced_items(pictures, 'car_id', 'cars', '_id', update_func)

#===============================================================================
# after_delete_car_picture ()
#===============================================================================
def after_delete_car_picture(picture):
    def update_func(car, picture):
        car['pictures'] = [ p for p in car['pictures'] if p['_id'] != picture['_id'] ]
        return car
    update_referenced_items(picture, 'car_id', 'cars', '_id', update_func)

#===============================================================================
# after_update_reputation ()
#===============================================================================
def after_update_reputation(reputation_new, reputation):
    reputation.update(reputation_new)
    after_replace_reputation(reputation, reputation)

#===============================================================================
# after_replace_reputation ()
#===============================================================================
def after_replace_reputation(reputation_new, reputation):
    def update_func(user, reputation):
        user['rating'] = reputation['reputation']
        return user
    update_referenced_items(reputation_new, 'user_id', 'users', '_id', update_func)

#===============================================================================
# before_insert_rides ()
#===============================================================================
def before_insert_rides(rides):
    for ride in rides if isinstance(rides, list) else [ rides ]:
        coordinates = ride['polyline']
        if 'coordinates' in coordinates:
            coordinates = coordinates.replace('coordinates=', '')
            ride['polyline'] = waypoints_to_polyline(coordinates)
        ride['polyline'] = downsample_polyline(ride['polyline'])

#===============================================================================
# before_delete_ride ()
#===============================================================================
def before_delete_ride(ride):
    collection = app.data.driver.db['lifts']
    for key in ride['lifts']:
        item = collection.find_one({'_id': key})
        if item['status'] in ['PENDING', 'ACTIVE']:
            collection.update({'_id': key}, {'$set': {'status': 'CANCELLED'}}, upsert = False)
            new_item = collection.find_one({'_id': key})
            after_updated_lift(new_item, item)

#===============================================================================
# before_insert_reports ()
#===============================================================================
def before_insert_reports(reports):
    for report in reports if isinstance(reports, list) else [ reports ]:
        report['timestamp'] = int(time.time())

#===============================================================================
# after_insert_reports ()
#===============================================================================
def after_insert_reports(reports):
    for report in reports if isinstance(reports, list) else [ reports ]:
        update_sites_reports_info(report)

#===============================================================================
# after_replace_report ()
#===============================================================================
def after_replace_report(updates, report):
    update_sites_reports_info(report)

#===============================================================================
# after_update_report ()
#===============================================================================
def after_update_report(updates, report):
    update_sites_reports_info(report)

#===============================================================================
# after_delete_report ()
#===============================================================================
def after_delete_report(report):
    update_sites_reports_info(report)

#===============================================================================
# before_insert_messages ()
#===============================================================================
def before_insert_messages(messages):
    for message in messages if isinstance(messages, list) else [ messages ]:
        message['timestamp'] = int(time.time())
        users = app.data.driver.db['users']
        sender = users.find_one({'_id': message['sender_id']})
        receiver = users.find_one({'_id': message['receiver_id']})
        message['sender_name'] = sender['name']
        message['receiver_name'] = receiver['name']

#===============================================================================
# after_insert_messages ()
#===============================================================================
def after_insert_messages(messages):
    for message in messages if isinstance(messages, list) else [ messages ]:
        post_process_data('messages', request, message)
        notification_thread_message(message['receiver_id'], message)

#===============================================================================
# remove_private_info ()
#===============================================================================
def remove_private_info(item, resource, request):
    ############################################################################
    #### Temporary, unsecure hack to remove the password from /users endpoint
    ############################################################################
    if resource == 'users':
        fields = [ 'password' ]
        if request.method == 'GET' and request.url.split('/')[-1] == 'users':
            remove_fields(item, fields)
    ############################################################################
    #### Temporary, unsecure hack to return the password in case of sign in
    #### with social id! We should probably switch to a different auth scheme
    #### than Basic Auth which requires client always sending username/password
    return
    ############################################################################

    if resource == 'users':
        fields = [ 'password' ]
        auth = request.authorization
        if request.method == 'POST' or \
           (auth and 'email' in item and item['email'] == auth['username']):
            # User is authorized
            return
        else:
            remove_fields(item, fields)

#===============================================================================
# filter_data ()
#===============================================================================
def filter_data(resource, request, data):
    apply_function(data, recursively_remove_fields, EVE_EXTRA_FIELDS)
    apply_function(data, remove_private_info, resource, request)
    return data

#===============================================================================
# finalize_payload ()
#===============================================================================
def finalize_payload(resource, request, response):
    data = str_to_json(response.get_data())
    data = flatten_data(data)
    data = filter_data(resource, request, data)
    if isinstance(data, list):
        data = {
            resource: data
        }
    response.set_data(json_to_str(data))

#===============================================================================
# add_location_header ()
#===============================================================================
def add_location_header(resource, request, response):
    assert request.method == 'POST'
    data = str_to_json(response.get_data())
    if 200 <= response.status_code <= 299:
        # Single item
        if resource not in data:
            response.headers.set('Location', '%s/%s' % (request.url, data['_id']))
        # List with one item
        elif resource in data and len(data) == 1 and len(data[resource]) == 1:
            response.headers.set('Location', '%s/%s' % (request.url, data[0]['_id']))
        # Multiple items were created, cannot set 'Location' header
        else:
            pass
    response.set_data(json_to_str(data))

#===========================================================================
# post_process_trip ()
#===========================================================================
def post_process_trip(trip, request):
    fields_to_expand = {
        # { 'new_field_name': [ 'reference_resource', 'reference_id' ], ... }
        # After expansion 'reference_id' will be removed.
        'driver': [ 'users', 'driver_id' ],
        'car': [ 'cars', 'car_id' ]
    }
    for step in trip['steps']:
        transport = step['transport']
        if transport['travel_mode'] == 'CAR_POOLING':
            for key in fields_to_expand:
                resource = fields_to_expand[key][0]
                field = fields_to_expand[key][1]
                collection = app.data.driver.db[resource]
                item = collection.find_one({'_id': str_to_oid(transport[field])})
                assert item
                filter_data(resource, request, item)
                transport[key] = item
                transport.pop(field)

#===========================================================================
# post_process_status ()
#===========================================================================
def post_process_status(lift, request):
    if 'driver_id' in request.args or 'passenger_id' in request.args:
        user_id = request.args['driver_id'] if 'driver_id' in request.args else request.args['passenger_id']
        collection = app.data.driver.db['feedbacks']
        item = collection.find_one({ '$and': [ {'lift_id': str_to_oid(lift['_id'])}, {'reviewer_id': str_to_oid(user_id)} ] })
        if item:
            lift['status'] = 'REVIEWED'
            
#===========================================================================
# post_process_lift ()
#===========================================================================
def post_process_lift(lift, request):
    post_process_trip(lift['trip'], request)
    post_process_status(lift, request)

#===========================================================================
# post_process_ride ()
#===========================================================================
def post_process_ride(ride, request):
    for lift in ride['lifts']:
        lift.pop('trip')
        users_col = app.data.driver.db['users']
        user = users_col.find_one({'_id': str_to_oid(lift['passenger_id'])})
        if user['pictures']:
            lift.update({'passenger_img': user['pictures'][0]['file']})

#===========================================================================
# post_process_feedback ()
#===========================================================================
def post_process_feedback(feedback, request):
    users = app.data.driver.db['users']
    reviewer = users.find_one({'_id': str_to_oid(feedback['reviewer_id'])})
    reviewed = users.find_one({'_id': str_to_oid(feedback['reviewed_id'])})
    feedback['reviewer'] = reviewer['name']
    feedback['reviewed_name'] = reviewed['name']

#===============================================================================
# post_process_data ()
#===============================================================================
def post_process_data(resource, request, data):
    func_to_apply = {
        'trips': post_process_trip,
        'lifts': post_process_lift,
        'rides': post_process_ride,
        'feedbacks': post_process_feedback,
    }
    if resource in func_to_apply:
        apply_function(data, func_to_apply[resource], request)

    objectids_to_strings(data)
    recursively_remove_fields(data, EVE_EXTRA_FIELDS)

    return data

#===============================================================================
# find_price ()
#===============================================================================
def find_price(leg, name):
    if leg['transport']['travel_mode'] == 'METRO':
        return metro_fare(name)
    elif leg['transport']['travel_mode'] == 'BUS':
        return bus_fare(leg, name)
    elif leg['transport']['travel_mode'] == 'RAIL':
        return rail_fare(leg['distance'], name)
    elif leg['transport']['travel_mode'] == 'TRAM':
        return tram_fare(leg, name)
    elif leg['transport']['travel_mode'] == 'CAR_POOLING':
        return carpooling_fare(leg['distance'], name)
    else:
    	return 0
 
#===============================================================================
# set_custom_payload ()
#===============================================================================
def set_custom_payload(resource, request, response):
    items = []

    if (resource in REQUIRED_PARAMS and
        not set(request.args).issuperset(REQUIRED_PARAMS[resource])):
            msg = 'Missing or invalid parameters' + \
                  ' (required: %s)' % ', '.join(REQUIRED_PARAMS[resource])
            response_set_error(response, 422, msg)
            return

    #---------------------------------------------------------------------------
    # /trips
    #---------------------------------------------------------------------------
    if resource == 'trips':
        trip_date = 'date=' + timestamp_to_datetime(request.args['start_date'], '%Y%m%d')
        trip_time = 'time=' + timestamp_to_datetime(request.args['start_date'], '%H:%M:%S')
        start_lat = 'slat=' + request.args['start_lat']
        start_lon = 'slng=' + request.args['start_lon']
        end_lat = 'tlat=' + request.args['end_lat']
        end_lon = 'tlng=' + request.args['end_lon']
        in_service = False
        fetched_site = None

        # Fetch collection 'sites' from db
        sites_collection = app.data.driver.db['sites']
        cursor = sites_collection.find({})
        # For every site in db
        for site in cursor:
            bb_minlat = site['bounding_box']['min_lat']
            bb_minlon = site['bounding_box']['min_lon']
            bb_maxlat = site['bounding_box']['max_lat']
            bb_maxlon = site['bounding_box']['max_lon']
            s_lat = float(request.args['start_lat'])
            s_lon = float(request.args['start_lon'])
            t_lat = float(request.args['end_lat'])
            t_lon = float(request.args['end_lon'])
            # Check if given coordinates are within a site's bounding box and retrieve url
            if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                in_service = True
                base_url = site['url']
                name = site['name']
                currency = site['price_info']['currency']
                fetched_site = site
        # If within a site's bounding box
        if in_service:
            full_url = "%s?%s&%s&%s&%s&%s&%s" % (base_url, trip_date, trip_time, start_lat, start_lon, end_lat, end_lon)
            app.logger.debug('%s' % (full_url))
            try:
                # GET request to Route Planning
                r = requests.get(full_url, timeout=38)
                json_extended_response = json.loads(r.text)
                if json_extended_response['result'] == True:
                    json_response = json_extended_response['data']
                else:
                    # TODO: Return error here
                    app.logger.debug('%s' % (json_extended_response['error']['message']))
                    json_response = []
            except requests.exceptions.Timeout:
                # TODO: Return error here
                app.logger.debug('Request to %s time out' % (full_url))
                json_response = []
        else:
            # TODO: Return error here
            app.logger.debug('Coordinates outside the site boundaries')
            json_response = []

        auth = request.authorization
        collection = app.data.driver.db['users']
        self_user = collection.find_one({'email': auth['username']})

        lifts_collection = app.data.driver.db['lifts']
        # Find all future lifts(no past lifts) created by user (as passenger) and confirmed by driver,if any
        fetched_lifts = list(lifts_collection.find({ '$and': [ {'passenger_id': self_user['_id']} , \
                                                        {'status': 'ACTIVE'} , \
                                                        {'start_point.date': {'$gte': int(time.time())}} , \
                                                        {'_deleted': {'$ne': True}}] }))

        # Find rides for which the user has already created a lift for
        fetched_rides = []
        if fetched_lifts:
            collection = app.data.driver.db['rides']
            for fetched_lift in fetched_lifts:
                lookup = {'_id': fetched_lift['ride_id']}
                fetched_ride = collection.find_one(lookup)
                fetched_rides.append(fetched_ride)

        trips = []
        # For each trip
        for trip in json_response:
            steps = []
            discard_trip = False
            bus_list = []
            travel_mode_list = []
            # For each leg
            for leg in trip['legs']:
                if leg['transport']['travel_mode'] in EXTENDED_TRAVEL_MODES:
                    leg['transport']['travel_mode'] = EXTENDED_TRAVEL_MODES[leg['transport']['travel_mode']]
                if leg['transport']['travel_mode'] in ALLOWED_TRAVEL_MODES:
                    if leg['transport']['travel_mode'] not in travel_mode_list:
                        travel_mode_list.append(leg['transport']['travel_mode'])
                    # If leg is carpooling
                    intermediate_points = []
                    if leg['transport']['travel_mode'] == 'CAR_POOLING':
                        # Set custom ride_id if carpooling is Mobalt shuttle
                        ride_id = leg['transport']['ride_id'] if leg['transport']['ride_id'] else '88e50050223f9badec44f5ff'
                        collection = app.data.driver.db['rides']
                        item = collection.find_one({'_id': str_to_oid(ride_id)})
                        # If user is not the driver of the ride and has not already created a lift for that ride
                        if oid_to_str(self_user['_id']) != oid_to_str(item['driver_id']) and item not in fetched_rides:
                            # If ride is external
                            if 'extras' in item:
                                # If ride is of other providers except Mobalt
                                if leg['transport']['ride_id']:
                                    public_uri = item['extras']['url']
                                # If ride is of Mobalt provider
                                else:
                                    user_name = self_user['name'].split(' ')[0]
                                    user_surname = self_user['name'].split(' ')[-1]
                                    user_email = self_user['email']
                                    user_phone = self_user['phone']
                                    start_address = leg['route']['points'][0]['address'] if leg['route']['points'][0]['address'] else 'Unknown address'
                                    starting_stop_name = leg['route']['points'][0]['address'] if leg['route']['points'][0]['address'] else 'Unknown address'
                                    starting_stop_time = leg['route']['points'][0]['departure_time']
                                    arrival_stop_name = leg['route']['points'][-1]['address'] if leg['route']['points'][0]['address'] else 'Unknown address'
                                    # Compose Mobalt URL parameters
                                    mobalt_url_params = ('&name=%s&surname=%s&email=%s&phone=%s&start_address=%s&starting_stop_name=%s&starting_stop_time=%s&arrival_stop_name=%s' % (user_name, user_surname, user_email, user_phone, start_address, starting_stop_name, starting_stop_time, arrival_stop_name))
                                    public_uri = (leg['transport']['route_url'] + mobalt_url_params)
                                
                                fetched_site['ride_details']['external'] = fetched_site['ride_details']['external'] + 1
                                transport = {
                                    'travel_mode': 'CAR_POOLING',
                                    'ride_id': ride_id, # rides['_id'] foreign key
                                    'driver_id': oid_to_str(item['driver_id']), # users['_id'] foreign key
                                    'car_id': oid_to_str(item['car_id']),  # cars['_id'] foreign key
                                    'public_uri': public_uri
                                }
                                # Dictionary containing information regarding external carpooling bookings
                                external_booking = {
                                    'uuid': item['extras']['uuid'],
                                    'url': item['extras']['url'],
                                    'username': self_user['email']
                                }
                                fetched_site['external_carpooling'].append(external_booking)
                            # If ride is internal
                            else:
                                fetched_site['ride_details']['internal'] = fetched_site['ride_details']['internal'] + 1
                                transport = {
                                    'travel_mode': 'CAR_POOLING',
                                    'ride_id': ride_id, # rides['_id'] foreign key
                                    'driver_id': oid_to_str(item['driver_id']), # users['_id'] foreign key
                                    'car_id': oid_to_str(item['car_id'])  # cars['_id'] foreign key
                                }
                            distance = int(float(leg['distance']))
                            sites_collection.update({'_id': fetched_site['_id']}, fetched_site, upsert = False)
                        # Else discard the ride
                        else:
                            discard_trip = True
                            break
                    # Else if leg is PT or feet
                    else:
                        # If transport name is empty replace with existing info
                        if not leg['transport']['short_name'] and not leg['transport']['long_name']:
                            route_short_name = leg['transport']['travel_mode']
                            route_long_name = leg['transport']['travel_mode']
                        elif not leg['transport']['short_name']:
                            route_short_name = '%s %s' % (leg['transport']['travel_mode'], leg['transport']['long_name'])
                            route_long_name = leg['transport']['long_name']
                        elif not leg['transport']['long_name']:
                            route_short_name = leg['transport']['short_name']
                            route_long_name = '%s %s' % (leg['transport']['travel_mode'], leg['transport']['short_name'])
                        else:
                            route_short_name = leg['transport']['short_name']
                            route_long_name = leg['transport']['long_name']
                        # if leg is FEET
                        if leg['transport']['travel_mode'] == 'FEET':
                            transport = {
                                'travel_mode': leg['transport']['travel_mode'],
                                'short_name': route_short_name,
                                'long_name': route_long_name 
                            }
                            distance = int(float(leg['distance']))
                        # if leg is PT
                        else:
                            transport = {
                                'travel_mode': leg['transport']['travel_mode'],
                                'short_name': route_short_name,
                                'long_name': route_long_name 
                            }
                            for point in leg['route']['points'][1:-1]:
                                med_point = {
                                    'point': {
                                        'lat': float(point['point']['lat']),
                                        'lon': float(point['point']['lon'])
                                    },
                                    'date': int(point['departure_time']),
                                    'address': point['address'] if point['address'] else 'Unknown address'
                                }
                                intermediate_points.append(med_point)
                            distance = int(float(leg['stops']))

                    step = {
                        'route': {
                            'start_point': {
                                'point': {
                                    'lat': float(leg['route']['points'][0]['point']['lat']),
                                    'lon': float(leg['route']['points'][0]['point']['lon'])
                                },
                                'date': int(leg['departure_time']),
                                'address': leg['route']['points'][0]['address'] if leg['route']['points'][0]['address'] else 'Unknown address'
                            },
                            'end_point': {
                                'point': {
                                    'lat': float(leg['route']['points'][-1]['point']['lat']),
                                    'lon': float(leg['route']['points'][-1]['point']['lon'])
                                },
                                'date': int(leg['departure_time']) + round(float(leg['duration']), 0),
                                'address': leg['route']['points'][-1]['address'] if leg['route']['points'][-1]['address'] else 'Unknown address'
                            },
                            'intermediate_points': intermediate_points
                        },
                        'transport': transport,
                        'price': {
                            'amount': find_price(leg, name),
                            'currency': currency
                        },
                        'distance': distance
                    }
                    # Further calculations for Ljubljana city bus
                    if name == 'Ljubljana' and leg['transport']['travel_mode'] == 'BUS' and leg['transport']['agency_id'] == 'lpp':
                        bus_list.append(step)
                        if len(bus_list) > 1:
                            # If changing bus within 90 minutes time frame do not issue a new ticket (step['price']['amount'] should be set to 0)
                            if step['route']['start_point']['date'] - bus_list[0]['route']['start_point']['date'] <= 5400:
                                # In case of changing zone within 90 minutes time frame modify ticket price accordingly if needed
                                if step['price']['amount'] > bus_list[0]['price']['amount']:
                                    for item in steps:
                                        if item == bus_list[0]:
                                            item['price']['amount'] = step['price']['amount']
                                # Fare for current bus is set to zero since less than 90 minutes have passed
                                step['price']['amount'] = 0
                            else:
                                bus_list = []
                                bus_list.append(step)
                    steps.append(step)
                else:
                    discard_trip = True
                    break
            if not discard_trip:
                # Find number of carpooling only, carpooling + PT and total number of offered solutions and update db
                if ('CAR_POOLING' in travel_mode_list) and (('METRO' in travel_mode_list) or ('BUS' in travel_mode_list) or ('RAIL' in travel_mode_list) or ('TRAM' in travel_mode_list)):
                    fetched_site['ride_details']['carpooling_PT'] = fetched_site['ride_details']['carpooling_PT'] + 1
                elif len(travel_mode_list) == 2 and 'CAR_POOLING' in travel_mode_list and 'FEET' in travel_mode_list:
                    fetched_site['ride_details']['carpooling_only'] = fetched_site['ride_details']['carpooling_only'] + 1
                elif len(travel_mode_list) == 1 and travel_mode_list[0] == 'CAR_POOLING':
                    fetched_site['ride_details']['carpooling_only'] = fetched_site['ride_details']['carpooling_only'] + 1
                fetched_site['ride_details']['total_solutions'] = fetched_site['ride_details']['total_solutions'] + 1
                sites_collection.update({'_id': fetched_site['_id']}, fetched_site, upsert = False)

                # Change end point address of FEET leg to next leg start point's address
                for i in range(0, len(steps)-2):
                    if steps[i]['transport']['travel_mode'] == 'FEET':
                        steps[i]['route']['end_point']['address'] = steps[i+1]['route']['start_point']['address']
                # Change start point address of FEET leg to previous leg end point's address
                for i in range(1, len(steps)-1):
                    if steps[i]['transport']['travel_mode'] == 'FEET':
                        steps[i]['route']['start_point']['address'] = steps[i-1]['route']['end_point']['address']

                trips.append({ 'steps': steps })
        if fetched_site is not None:
            if self_user['email'] not in fetched_site['users']:
                fetched_site['users'].append(self_user['email'])
                sites_collection.update({'_id': fetched_site['_id']}, fetched_site, upsert = False)
        items = trips

    #---------------------------------------------------------------------------
    # /rides_boundary
    #---------------------------------------------------------------------------
    elif resource == 'rides_boundary':
        min_lat = float(request.args['min_lat'])
        min_lon = float(request.args['min_lon'])
        max_lat = float(request.args['max_lat'])
        max_lon = float(request.args['max_lon'])

        if request.args['site'] == 'brussels':
            site_name = 'Brussels'
        elif request.args['site'] == 'edinburgh':
            site_name = 'Edinburgh'
        elif request.args['site'] == 'ljubljana':
            site_name = 'Ljubljana'
        elif request.args['site'] == 'ticino':
            site_name = 'Canton Ticino'

        # Fetch collection 'sites' from db
        sites_collection = app.data.driver.db['sites']
        site = sites_collection.find_one({'name': site_name})
        
        lookup1 = { '$and': [ {'end_point.lat': {'$gte': min_lat}} , \
                            {'end_point.lat': {'$lte': max_lat}} , \
                            {'end_point.lon': {'$gte': min_lon}} , \
                            {'end_point.lon': {'$lte': max_lon}} ] }

        lookup2 = { '$and': [ {'start_point.lat': {'$gte': min_lat}} , \
                            {'start_point.lat': {'$lte': max_lat}} , \
                            {'start_point.lon': {'$gte': min_lon}} , \
                            {'start_point.lon': {'$lte': max_lon}} ] }

        lookup3 = { '$and': [ {'_deleted': {'$eq': False}} , \
                            {'activated': {'$eq': True}} , \
                            {'date': {'$gt': site['carpooling_info']['nightly_updated']}} ] }           

        lookup = { '$and': [ lookup1, lookup2, lookup3 ] }
        cursor = app.data.driver.db['rides'].find(lookup)
        rides = []
        for ride in cursor:
            rides.append(ride)
        items = { 'rides': rides }
        apply_function(items, recursively_remove_fields, EVE_EXTRA_FIELDS)

    #---------------------------------------------------------------------------
    # /rides_internal
    #---------------------------------------------------------------------------
    elif resource == 'rides_internal':
        lookup = { 'extras': {'$exists': False} }
        cursor = app.data.driver.db['rides'].find(lookup)
        rides = []
        for ride in cursor:
            rides.append(ride)
        items = { 'rides': rides }
        apply_function(items, recursively_remove_fields, EVE_EXTRA_FIELDS)

    #---------------------------------------------------------------------------
    # /sites_boundary
    #---------------------------------------------------------------------------
    elif resource == 'sites_boundary':
        min_lat = float(request.args['min_lat'])
        min_lon = float(request.args['min_lon'])
        max_lat = float(request.args['max_lat'])
        max_lon = float(request.args['max_lon'])

        lookup = { '$and': [ {'bounding_box.min_lat': {'$lte': min_lat}} , \
                            {'bounding_box.min_lon': {'$lte': min_lon}} , \
                            {'bounding_box.max_lat': {'$gte': max_lat}} , \
                            {'bounding_box.max_lon': {'$gte': max_lon}} ] }
        cursor = app.data.driver.db['sites'].find(lookup)
        sites = []
        for site in cursor:
            sites.append(site)
        items = { 'sites': sites }
        apply_function(items, recursively_remove_fields, EVE_EXTRA_FIELDS)

    #---------------------------------------------------------------------------
    # /reports_boundary
    #---------------------------------------------------------------------------
    elif resource == 'reports_boundary':
        min_lat = float(request.args['min_lat'])
        min_lon = float(request.args['min_lon'])
        max_lat = float(request.args['max_lat'])
        max_lon = float(request.args['max_lon'])

        lookup = { '$and': [ {'location.geometry.coordinates.1': {'$gte': min_lat}} , \
                            {'location.geometry.coordinates.0': {'$gte': min_lon}} , \
                            {'location.geometry.coordinates.1': {'$lte': max_lat}} , \
                            {'location.geometry.coordinates.0': {'$lte': max_lon}}, \
                            {'_deleted': {'$ne': True}} ] }
        cursor = app.data.driver.db['reports'].find(lookup)
        reports = []
        for report in cursor:
            reports.append(report)
        items = { 'reports': reports }
        apply_function(items, recursively_remove_fields, EVE_EXTRA_FIELDS)

    #---------------------------------------------------------------------------
    # /reports_around
    #---------------------------------------------------------------------------
    elif resource == 'reports_around':
        lon = float(request.args['lon'])
        lat = float(request.args['lat'])
        radius = km2rad(request.args.get('radius', REPORTS_AROUND_RADIUS_KM))

        lookup = { '$and': [ {'location.geometry': {'$geoWithin': {'$centerSphere': [ [lon, lat], radius ] }}}, \
                            {'_deleted': {'$ne': True}} ] }
        cursor = app.data.driver.db['reports'].find(lookup)
        reports = []
        for report in cursor:
            reports.append(report)
        items = { 'reports': reports }
        apply_function(items, recursively_remove_fields, EVE_EXTRA_FIELDS)

    #---------------------------------------------------------------------------
    # /positions_button
    #---------------------------------------------------------------------------
    elif resource == 'positions_button':
        driver_lon = float(request.args['lon'])
        driver_lat = float(request.args['lat'])
        lift_id = str_to_oid(request.args['lift_id'])

        lift = app.data.driver.db['lifts'].find_one({'_id': lift_id})
        distance = haversine_formula(driver_lon, driver_lat, lift['start_point']['point']['lon'], lift['start_point']['point']['lat'])
        eta = int((distance / MEAN_VELOCITY) * 60)
        if distance <= RADIUS:
            # print("    Passenger %s got notified that driver %s is %skm away. Estimated time of arrival: %smin" % (lift['passenger_id'], lift['driver_id'], distance, eta))
            # TODO: Send push notification here - PushMessagingServer.send(to=passenger_FCM_token, payload_data={'lift_id':lift_id, 'distance':distance ,'eta':eta})
            send_push_notification_eta(oid_to_str(lift['passenger_id']), {'lift_id': oid_to_str(lift['_id']),'distance':distance ,'eta':eta})
            items = { 'status': 'OK', 'details': 'Passenger will be notified that you are close to the pickup point.' }
        else:
            items = { 'status': 'KO', 'details': 'You are not so close to the passenger pickup point.' }

    #---------------------------------------------------------------------------
    # /stops
    #---------------------------------------------------------------------------
    elif resource == 'stops':
        lon = float(request.args['lon'])
        lat = float(request.args['lat'])
        radius = km2rad(request.args.get('radius', STOPS_AROUND_RADIUS_KM))
        lookup = {'loc': {'$geoWithin': {'$centerSphere': [ [lon, lat], radius ] }}}
        cursor = app.data.driver.db['stops'].find(lookup)
        stops = []
        for stop in cursor:
            # In MongoDB the coordinates is always a list of [lot, lan]
            stop['lon'] = stop['loc']['coordinates'][0]
            stop['lat'] = stop['loc']['coordinates'][1]
            stop.pop('loc')
            stop['transits'] = sorted(stop['transits'], key=lambda k: k['transport']['short_name'])
            stops.append(stop)
        items = { 'stops': stops }

    #---------------------------------------------------------------------------
    # /waiting_times
    #---------------------------------------------------------------------------
    elif resource == 'waiting_time':
        # TODO: Bad hack. Change app requests from .../waiting-time/87408 to
        # .../waiting-time?stop_code=87408&time=10:33:00
        stop_code = request.url.split('/')[-1]
        # stop_code = request.args.get('stop_code')
        cur_time = '12:33:00'
        # cur_time = request.args.get('time')
        stop = app.data.driver.db['stops'].find_one({'stop_code': stop_code})
        departure_times = app.data.driver.db['departures'].find_one({'stop_code': stop_code})
        if not stop or not departure_times:
            items = {}
        else:
            assert stop
            assert departure_times
            for transit in stop['transits']:
                route_short_name = transit['transport']['short_name']
                transit['stop_distance'] = random.randint(1,10)  # TODO: will be replaced with real-time info
                transit['waiting_time'] = random.randint(1,10)  # TODO: will be replaced with real-time info
                transit['terminus_departure_time'] = []
                all_times = departure_times['transits'][route_short_name]
                # Find the position where 'time' whould be inserted in
                # 'all_times'; get N entries around it (1 prev and N-1 next).
                N = 3
                p = bisect.bisect(all_times, cur_time)
                start = max(0, p - 1)
                end = min(len(all_times), p + N - 1)
                close_times = all_times[start:end]
                for t in close_times:
                    hour, minutes, seconds = t.split(':')
                    transit['terminus_departure_time'].append({
                        'hour': hour,
                        'minute': minutes,
                    })
            items = stop

    objectids_to_strings(items)
    data = {
        '_items': items
    }
    response.set_data(json_to_str(data))
    response.headers.set('X-Total-Count', len(data['_items']))

#===============================================================================
# data_group_by ()
#===============================================================================
def data_group_by(data, group_key):
    group_items = defaultdict(list)
    for item in data:
        group = item[group_key]
        item.pop(group_key)
        group_items[group].append(item)

    del data[:]
    new_data = [ {group_key: k, 'items': group_items[k]} for k in group_items ]
    data.extend(new_data)

#===============================================================================
# disable_filters ()
#===============================================================================
def disable_filters(request):
    if request.args:
        # Hack to remove fields because request.args is immutable
        args = dict(request.args)
        remove_fields(args, [ 'where', 'projection', 'sort', 'aggregation' ])
        request.args = ImmutableMultiDict(args)

#===============================================================================
# before_GET ()
#===============================================================================
def before_GET(resource, request, lookup):

    resource = actual_resource(request)

    #---------------------------------------------------------------------------
    # Disable filters such as 'where', 'projection' etc
    #---------------------------------------------------------------------------
    disable_filters(request)

    #---------------------------------------------------------------------------
    # Search based on secondary fields
    #---------------------------------------------------------------------------
    # 'lookup': empty if GET on a resource point, non-empty if GET on item
    if not lookup and request.args:
        allowed_fields = ['_id'] + RESOURCE_SEARCH_FIELDS.get(resource, [])
        for field in set(request.args).intersection(allowed_fields):
            # Field does not contain a special operator
            if '_$' not in field:
                values = request.args[field].split(GET_VALUES_SEPARATOR)
                lookup.update({field: {'$in': values }})
            else:
                value = float(request.args[field])  # TODO: don't always cast to float
                field, operator = field.split('_$')
                operator = '$' + operator
                if field not in lookup:
                    lookup.update({field: {operator: value}})
                else:  # Add new operator to existing
                    lookup[field].update({operator: value})

    #---------------------------------------------------------------------------
    # Auto-embed (replace object ids with objects)
    #---------------------------------------------------------------------------
    if resource in AUTO_EMBED_FIELDS:
        fields = [ '"%s":1' % f for f in AUTO_EMBED_FIELDS[resource] ]
        args = dict(request.args)
        args.update({'embed': '{' + ','.join(fields) + '}'})
        request.args = ImmutableMultiDict(args)

#===============================================================================
# after_GET ()
#===============================================================================
def after_GET(resource, request, response):

    #---------------------------------------------------------------------------
    # Custom endpoint
    #---------------------------------------------------------------------------
    if resource in CUSTOM_ENDPOINTS:
        set_custom_payload(resource, request, response)

    #---------------------------------------------------------------------------
    # If status code not 2XX, no need to further process response content
    #---------------------------------------------------------------------------
    # 304: object was not modified since last GET from client. Payload will be
    # empty and client will use its own cached object
    # 401: unauthorized access
    # 404: object not found or deleted. In case we soft deletes are enabled, Eve
    # returns the full deleted object along with the error code, so make sure
    # we only return the error code and error message (not the object)
    #---------------------------------------------------------------------------
    if not 200 <= response.status_code < 300:
        if response.status_code != 304:
            data = str_to_json(response.get_data())
            response.set_data(json_to_str({ '_error': data['_error'] }))
        return

    resource = actual_resource(request)

    data = str_to_json(response.get_data())
    data = flatten_data(data)

    #---------------------------------------------------------------------------
    # Add, remove or modify fields before returning data to client
    #---------------------------------------------------------------------------
    data = post_process_data(resource, request, data)

    #---------------------------------------------------------------------------
    # Group data by key if required
    #---------------------------------------------------------------------------
    for group_key in RESOURCE_GROUP_BY_FIELDS.get(resource, []):
        if 'group_by_' + group_key in request.args:
            data_group_by(data, group_key)
            break  # In case more than one group_by_* args provided

    response.set_data(json_to_str(data))
    finalize_payload(resource, request, response)

#===============================================================================
# before_POST ()
#===============================================================================
def before_POST(resource, request):
    pass

#===============================================================================
# after_POST ()
#===============================================================================
def after_POST(resource, request, response):
    if response.status_code == 201:
        act_resource = actual_resource(request)
        if act_resource == 'feedbacks':
            data = str_to_json(response.get_data())
            items = data['_items'] if '_items' in data else [ data ]
            for item in items:
                post_process_feedback(item, request)
            response.set_data(json_to_str(data))

    finalize_payload(resource, request, response)
    add_location_header(resource, request, response)
    # In case email already exists, return 409 status code
    if resource == 'users' and response.status_code == 422:
        data = str_to_json(response.get_data())
        if ('email' in data['_issues'] and
           'is not unique' in data['_issues']['email']):
            response.status_code = 409
            data['_error']['code'] = str(response.status_code)
            response.set_data(json_to_str(data))

#===============================================================================
# before_PUT ()
#===============================================================================
def before_PUT(resource, request, lookup):
    pass

#===============================================================================
# after_PUT ()
#===============================================================================
def after_PUT(resource, request, response):
    finalize_payload(resource, request, response)

#===============================================================================
# before_PATCH ()
#===============================================================================
def before_PATCH(resource, request, lookup):
    pass

#===============================================================================
# after_PATCH ()
#===============================================================================
def after_PATCH(resource, request, response):
    finalize_payload(resource, request, response)

#===============================================================================
# before_DELETE ()
#===============================================================================
def before_DELETE(resource, request, lookup):
    pass

#===============================================================================
# after_DELETE ()
#===============================================================================
def after_DELETE(resource, request, response):
    finalize_payload(resource, request, response)
 
#===============================================================================
# item_deleted ()
#===============================================================================
def item_deleted(item):
    return '_deleted' in item and item['_deleted']

#===============================================================================
# my_basic_auth ()
#===============================================================================
class my_basic_auth(BasicAuth):
    def check_auth(self, username, password, allowed_roles, resource, method):
        if resource == 'feedbacks_all':
            resource = 'feedbacks'

        # Check if url does not require authentication
        if resource in AUTH_FREE_URLS and method in AUTH_FREE_URLS[resource]:
            # All params must exist in url
            params = AUTH_FREE_URLS[resource][method]
            if all([ param in request.url for param in params ]):
                return True

        # Check if user is an admin
        admin = app.data.driver.db['admins'].find_one({'username': username})
        if admin and admin['password'] == password and not item_deleted(admin):
            return True

        # Check if user is authenticated
        user = app.data.driver.db['users'].find_one({'email': username})
        if not user or item_deleted(user):
            return False
        authenticated = (user['password'] == password)

        # Check if user is authorized
        authorized = False
        if method in [ 'PUT', 'PATCH', 'DELETE' ]:
            try:
                oid = str_to_oid(request.url.split('/')[6].split('?')[0])
            except:
                oid = None
            item = app.data.driver.db[resource].find_one({'_id': oid})
            # In case item is deleted, authorize user so [s]he gets a 404 error
            # rather than a '401: Provide proper credentials' error
            if item and item_deleted(item):
                authorized = True
            elif item and OWNER_FIELD in item and username in item[OWNER_FIELD]:
                authorized = True
        else:
            assert method in [ 'POST', 'GET' ]
            authorized = True

        return authenticated and authorized

#===============================================================================
# notification_thread_lift ()
#===============================================================================
def notification_thread_lift(user_id, lift):
    
    # send_push_notification ()
    # The copy_current_request_context decorator ensures that the HTTP request that is active when a function is called
    # remains active even when the function is subsequently executed in a thread
    @copy_current_request_context
    def send_push_notification(user_id, message):
        message['type'] = 'lift'
        assert isinstance(user_id, str)
        assert isinstance(message, dict)
        user_id = str_to_oid(user_id)
        message = filter_data(actual_resource(request), request, message)
        
        user = app.data.driver.db['users'].find_one({'_id': user_id})
        assert user and user['_id'] == user_id
        fcm_token = user['fcm_token']
        platform = user['platform'] if 'platform' in user else 'ANDROID'

        # if user platform is iOS send custom payload
        if platform == 'IOS':
            message = {
                '_id': message['_id'],
                'passenger_id': message['passenger_id'],
                'driver_id': message['driver_id'],
                'ride_id': message['ride_id'],
                'car_id': message['car_id'],
                'status': message['status']
            }
            platform_url = 'FCMConnectorService/messaging/notification-message/send'
            data_str = '%s' % (message)
            data_str = remove_non_ascii(data_str)
            data_title = "Sample_Title"
            if message['status'] == 'PENDING':
                notification_title = "REQUEST_LIFT_TO_DRIVER_TITLE"
                notification_body = "REQUEST_LIFT_TO_DRIVER_BODY"
            elif message['status'] == 'ACTIVE':
                notification_title = "ACCEPTED_LIFT_TITLE"
                notification_body = "ACCEPTED_LIFT_BODY"
            elif message['status'] == 'REFUSED':
                notification_title = "REFUSED_LIFT_TITLE"
                notification_body = "REFUSED_LIFT_BODY"
            elif message['status'] == 'CANCELLED':
                notification_title = "CANCELLED_LIFT_TITLE"
                notification_body = "CANCELLED_LIFT_BODY"
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
    t = threading.Thread(target = send_push_notification, args = [user_id, lift])
    t.start()

#===============================================================================
# notification_thread_message ()
#===============================================================================
def notification_thread_message(user_id, message):
    
    # send_push_notification ()
    # The copy_current_request_context decorator ensures that the HTTP request that is active when a function is called
    # remains active even when the function is subsequently executed in a thread
    @copy_current_request_context
    def send_push_notification(user_id, message):
        message['type'] = 'message'
        assert isinstance(user_id, str)
        assert isinstance(message, dict)
        user_id = str_to_oid(user_id)
        message = filter_data(actual_resource(request), request, message)
        
        user = app.data.driver.db['users'].find_one({'_id': user_id})
        assert user and user['_id'] == user_id
        fcm_token = user['fcm_token']
        platform = user['platform'] if 'platform' in user else 'ANDROID'

        # if user platform is iOS send custom payload
        if platform == 'IOS':
            platform_url = 'FCMConnectorService/messaging/notification-message/send'
            data_str = '%s' % (message)
            data_str = remove_non_ascii(data_str)
            data_title = "Sample_Title"
            notification_title = "MESSAGE_TITLE"
            notification_body = "MESSAGE_BODY"
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
    t = threading.Thread(target = send_push_notification, args = [user_id, message])
    t.start()

#===============================================================================
# send_push_notification_eta ()
#===============================================================================
def send_push_notification_eta(user_id, message):
    message['type'] = 'eta'
    assert isinstance(user_id, str)
    assert isinstance(message, dict)
    user_id = str_to_oid(user_id)
    message = filter_data(actual_resource(request), request, message)

    user = app.data.driver.db['users'].find_one({'_id': user_id})
    assert user and user['_id'] == user_id
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
# check_auth_for_statistics ()
#===============================================================================
def check_auth_for_statistics(username, password):
    #This function is called to check if a username password combination belongs to an admin user.
    
    # Check if user is an admin
    admin = app.data.driver.db['admins'].find_one({'username': username})
    if admin and admin['password'] == password and not item_deleted(admin):
        return True
    return False

#===============================================================================
# authenticate ()
#===============================================================================
def authenticate():
    #Sends a 401 response that enables basic auth
    return Response(
    'Could not verify your access level for that URL.\n'
    'You have to login with proper credentials', 401,
    {'WWW-Authenticate': 'Basic realm="Login Required"'})

#===============================================================================
# requires_auth ()
#===============================================================================
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth_for_statistics(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


#===============================================================================
# update_sites_carpool_info ()
#===============================================================================
def update_sites_carpool_info(ride):
    # Fetch collection 'sites' from db
    collection = app.data.driver.db['sites']
    cursor = collection.find({})
    # For every site in db
    for site in cursor:
        bb_minlat = site['bounding_box']['min_lat']
        bb_minlon = site['bounding_box']['min_lon']
        bb_maxlat = site['bounding_box']['max_lat']
        bb_maxlon = site['bounding_box']['max_lon']
        s_lat = ride['start_point']['lat']
        s_lon = ride['start_point']['lon']
        t_lat = ride['end_point']['lat']
        t_lon = ride['end_point']['lon']
        # Check ii given coordinates are within a site's bounding box and take url
        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
            site['carpooling_info']['version'] = site['carpooling_info']['version'] + 1
            site['carpooling_info']['updated'] = int(time.time())
            collection.update({'_id': site['_id']}, site, upsert = False)

#===============================================================================
# update_sites_reports_info ()
#===============================================================================
def update_sites_reports_info(reports):
    # Fetch collection 'sites' from db
    collection = app.data.driver.db['sites']
    cursor = collection.find({})
    # For every site in db
    for site in cursor:
        bb_minlat = site['bounding_box']['min_lat']
        bb_minlon = site['bounding_box']['min_lon']
        bb_maxlat = site['bounding_box']['max_lat']
        bb_maxlon = site['bounding_box']['max_lon']
        s_lat = reports['location']['geometry']['coordinates'][1]
        s_lon = reports['location']['geometry']['coordinates'][0]
        t_lat = reports['location']['geometry']['coordinates'][1]
        t_lon = reports['location']['geometry']['coordinates'][0]
        # Check ii given coordinates are within a site's bounding box and take url
        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
            site['reports_info']['version'] = site['reports_info']['version'] + 1
            site['reports_info']['updated'] = int(time.time())
            collection.update({'_id': site['_id']}, site, upsert = False)

#===============================================================================
# main ()
#===============================================================================
app = Eve(auth=my_basic_auth, settings=os.path.join(SCRIPT_PATH, 'settings.py'), static_folder=STATISTICS_SCRIPT_FOLDER)

# Database event hooks
app.on_insert += before_insert
app.on_update += before_update
app.on_replace += before_replace
app.on_delete_item += before_delete  # required for soft deletes

app.on_inserted_users += after_insert_users
app.on_inserted_cars += after_insert_cars
app.on_inserted_rides += after_insert_rides
app.on_deleted_item_rides += after_delete_ride
app.on_replaced_rides += after_replace_ride
app.on_updated_rides += after_update_ride
app.on_deleted_item_cars += after_delete_car
app.on_inserted_lifts += after_insert_lifts
app.on_replaced_lifts += after_replaced_lift
app.on_updated_lifts += after_updated_lift
app.on_deleted_item_lifts += after_delete_lift
app.on_inserted_user_pictures += after_insert_user_pictures
app.on_deleted_item_user_pictures += after_delete_user_picture
app.on_inserted_car_pictures += after_insert_car_pictures
app.on_deleted_item_car_pictures += after_delete_car_picture
app.on_updated_reputations += after_update_reputation
app.on_replaced_reputations += after_replace_reputation
app.on_insert_rides += before_insert_rides
app.on_delete_item_rides += before_delete_ride
app.on_insert_reports += before_insert_reports
app.on_inserted_reports += after_insert_reports
app.on_deleted_item_reports += after_delete_report
app.on_replaced_reports += after_replace_report
app.on_updated_reports += after_update_report
app.on_insert_messages += before_insert_messages
app.on_inserted_messages += after_insert_messages

# Requests event hooks
app.on_pre_GET += before_GET
app.on_post_GET += after_GET
app.on_pre_POST += before_POST
app.on_post_POST += after_POST
app.on_pre_PATCH += before_PATCH
app.on_post_PATCH += after_PATCH
app.on_pre_PUT += before_PUT
app.on_post_PUT += after_PUT
app.on_pre_DELETE += before_DELETE
app.on_post_DELETE += after_DELETE

CORS(app)
Bootstrap(app)
url_prefix = '/%s/%s/%s' % (URL_PREFIX, API_VERSION, 'docs')
app.register_blueprint(eve_docs, url_prefix=url_prefix)

# Setup Sentry so we get notified whenever an unhandled exception happens
if USE_SENTRY:
    sentry = raven.Client(SENTRY_DSN)
    sentry.captureMessage('Server started')

    # Use Sentry to also send notifications in case an entry of level ERROR or
    # CRITICAL is logged
    sentry_handler = SentryHandler(sentry)
    sentry_handler.setLevel(logging.ERROR)
    setup_logging(sentry_handler)
    app.logger.addHandler(sentry_handler)

#===============================================================================
# log_request ()
#===============================================================================
@app.before_request
def log_request():
    data = str(request.data.decode()) if request.data else ''
    user = request.authorization['username'] if request.authorization else None
    if user not in EXCLUDE_FROM_LOGS:
        app.logger.debug('%s Request %s' % (user, data))

#===============================================================================
# log_response ()
#===============================================================================
@app.after_request
def log_response(response):
    if response.content_type == 'application/json':
        data = str(response.data.decode()) if response.data else ''
    else:
        data = '<content type not json>'
    user = request.authorization['username'] if request.authorization else None
    if user not in EXCLUDE_FROM_LOGS:
        app.logger.debug('%s Response %s' % (user, data))
    return response

#===============================================================================
# errorhandler ()
#===============================================================================
@app.errorhandler(Exception)
def all_exception_handler(exception):
    app.logger.exception(exception)
    if USE_SENTRY:
        send_exception_info_to_sentry()
    if DEBUG:
        # Re-raise exception, e.g. to get interactive console in browser
        raise exception
    else:
        # Else return 500 error message to client
        return make_response('Internal server error', 500)

#===============================================================================
# print_statistics ()
#===============================================================================
@app.route('/statistics')
@requires_auth
# Custom endpoint for printing statistics (e.g http://127.0.0.1:5000/statistics, not http://127.0.0.1:5000/URL_PREFIX/API_VERSION/statistics)
def print_statistics():
    statistics_main(MONGO_DBNAME)
    return send_from_directory(STATISTICS_SCRIPT_FOLDER, 'statistics.html')

#===============================================================================
# print_statistics_csv ()
#===============================================================================
@app.route('/statisticsCSV')
@requires_auth
# Custom endpoint for creating statistics CSV files (e.g http://127.0.0.1:5000/statisticsCSV, not http://127.0.0.1:5000/URL_PREFIX/API_VERSION/statisticsCSV)
def print_statistics_csv():
    statisticsCSV_main(MONGO_DBNAME)
    return send_from_directory(STATISTICS_SCRIPT_FOLDER, 'user_activity.csv')

#===============================================================================
# send_exception_info_to_sentry ()
#===============================================================================
def send_exception_info_to_sentry():
    user_context = {
        'user': request.authorization['username'] if request.authorization else None,
        'method': request.method,
        'endpoint': request.endpoint,
        'url_base': request.base_url,
        'url_path': request.path,
        'url_args': request.args,
        'url_full': request.url,
        'remote_addr': request.remote_addr,
        'request_data': str(request.data.decode()) if request.data else '',
        'request_headers': request.headers.to_list(),
    }
    sentry.user_context(user_context)
    sentry.captureException()

#---------------------------------------------------------------------------
# Setup logging
#---------------------------------------------------------------------------
if LOG_EVERY_REQ_AND_RES:

    # Set level of default stdout logger to INFO (e.g. don't show DEBUG entries)
    def_stdout_handler = app.logger.handlers[0]
    def_stdout_handler.setLevel(logging.INFO)

    # Enable also logging to file (create new log file when size reaches 10MB)
    file_handler = logging.handlers.RotatingFileHandler(
         os.path.join(SCRIPT_PATH, '../logs', 'log'), maxBytes=1000000, backupCount=1000)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s %(clientip)s %(message)s'
        ' CONTEXT: %(method)s %(url)s %(filename)s:%(lineno)d'))
    file_handler.setLevel(logging.DEBUG)
    app.logger.addHandler(file_handler)

    # This must be set to the minimum level of all loggers
    app.logger.setLevel(logging.DEBUG)

    # Log git commit used
    try:
        cmd = ['git', 'describe', '--always', '--dirty']
        print('Git version: %s' % subprocess.check_output(cmd, cwd=SCRIPT_PATH).decode().strip())
    except FileNotFoundError:
        print('Git version: git not installed')
