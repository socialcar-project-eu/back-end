import sys
import os
import pymongo
import argparse
import requests
import hashlib
import hmac
import json
import time, datetime, threading
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from socialcar.utils import waypoints_to_polyline, generate_custom_objectid, str_to_oid, oid_to_str, inside_bounding_box

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_RIDES_COLLECTION = 'rides'
MONGO_SITES_COLLECTION = 'sites'

CITIES = [ 'brussels', 'edinburgh', 'ljubljana', 'ticino' ]
brussels_driver_id = None
edinburgh_driver_id = None
ljubljana_driver_id = None
ticino1_driver_id = None
ticino2_driver_id = None
brussels_car_id = None
edinburgh_car_id = None
ljubljana_car_id = None
ticino1_car_id = None
ticino2_car_id = None

#===============================================================================
# date_to_sec()
#===============================================================================
def date_to_sec(date_str, date_format):
    return time.mktime(datetime.datetime.strptime(date_str, date_format).timetuple())

#===============================================================================
# time_to_sec ()
#===============================================================================
def time_to_sec(time_str):
    h, m = time_str.split(':')
    return int(h) * 3600 + int(m) * 60

#===============================================================================
# periodic_pull ()
#===============================================================================
def periodic_pull(host, port, interval, period, radius, dbname, city, use_ssl):
    print('%s - Checking for external rides...' % (datetime.datetime.utcnow().strftime('%d-%m-%Y @ %H:%M:%S (UTC)')))

    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    rides_collection = db[MONGO_RIDES_COLLECTION]
    sites_collection = db[MONGO_SITES_COLLECTION]
    ids_to_keep = []
    counter_api = 0

    prefix = "https" if use_ssl else "http"

    # Disable SSL warnings
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # Request Timestamp
    timestamp = int(time.time())

    if city == 'brussels':
        # Set private key for test server
        # privateKey = "qUqxRCTZhf5XDEq8F7mMWnVbP4QSHfgJsAv5H65pTJG"
        # Set private key for main server
        privateKey = "yYDyFQN4v51Fi4vx513z9f1ERv74BgSuVzI4IeSW3SZ"
        # Set public key for test server
        # publicKey = "sc_dimitris_tsoukalas_live"
        # Set public key for main server
        publicKey = "tx_socialcar_server"
        # Set base url
        baseUrl = "https://api.carpool.be/rdexapi/"
        # Set call
        call = "period.json"
        # Create extra values
        areaCode = "BE-BRU"
        # Compose unsigned URL
        unSingnedUrl = "%s%s?timestamp=%s&apikey=%s&area_code=%s&period=%s&distance=%s" % (baseUrl, call, timestamp, publicKey, areaCode, period, radius)
        # Convert private key to bytes
        privateKeyToBytes = bytearray(privateKey, "ASCII")
        # Convert unsigned URL to bytes
        unSingnedUrlToBytes = bytearray(unSingnedUrl,"ASCII")
        # Create the signature
        # Hash the unsigned url with the 'sha256’-algorithm using the private key
        sign = hmac.new(privateKeyToBytes, unSingnedUrlToBytes, hashlib.sha256).hexdigest()
        # Compose signed url
        signedUrl = "%s&signature=%s" % (unSingnedUrl, sign)
    elif city == 'edinburgh':
        # Set private key
        privateKey = "WPEbb4uJDL76VVc6pmBCrE7BL27L5QQiekuSJJpm"
        # Set public key
        publicKey = "socialcar"
        # Set base url
        baseUrl = "https://api.liftshare.com/rdex/v1/"
        # Set call
        call = "period"
        # compose unsigned URL
        unSingnedUrl = "%s%s?timestamp=%s&apikey=%s&period=%s" % (baseUrl, call, timestamp, publicKey, period)
        # Convert private key to bytes
        privateKeyToBytes = bytearray(privateKey, "ASCII")
        # Convert unsigned URL to bytes
        unSingnedUrlToBytes = bytearray(unSingnedUrl,"ASCII")
        # Create the signature
        # Hash the unsigned url with the 'sha256’-algorithm using the private key
        sign = hmac.new(privateKeyToBytes, unSingnedUrlToBytes, hashlib.sha256).hexdigest()
        # Compose signed url
        signedUrl = "%s&signature=%s" % (unSingnedUrl, sign)
    elif city == 'ljubljana':
        signedUrl = "https://prevoz.org/api/search/socialcar/?format=json"
    elif city == 'ticino':
        # Set private key
        privateKey = "A93reRTUJHsCuQSHR+L3GxqOJyDmQpCgps102ciuabc="
        # Set public key
        publicKey = "SocialCar"
        # Set base url
        baseUrl = "https://ws.bepooler.ch/socialcar/"
        # Set call
        call = "period"
        # Create extra values
        areaCode = "CH"
        # compose unsigned URL
        unSingnedUrl = "%s%s?timestamp=%s&apikey=%s&area_code=%s&period=%s&distance=%s" % (baseUrl, call, timestamp, publicKey, areaCode, period, radius)
        # Convert private key to bytes
        privateKeyToBytes = bytearray(privateKey, "ASCII")
        # Convert unsigned URL to bytes
        unSingnedUrlToBytes = bytearray(unSingnedUrl,"ASCII")
        # Create the signature
        # Hash the unsigned url with the 'sha256’-algorithm using the private key
        sign = hmac.new(privateKeyToBytes, unSingnedUrlToBytes, hashlib.sha256).hexdigest()
        # Compose signed url
        signedUrl = "%s&signature=%s" % (unSingnedUrl, sign)

    # GET request
    headers = {'content-type': 'application/json'}
    r = requests.get(signedUrl, headers=headers, verify=False)

    if r.status_code == 200:
        rides = []

        auth = HTTPBasicAuth('admin', 'password') # TODO: Insert admin credentials here
        headers = {'content-type': 'application/json'}

        #===============================================================================
        # POST fetched rides to server
        #===============================================================================
        res_json = json.loads(r.text)
        counter = 0

        # Add delay for Edinburgh to update rides after 00:00
        if city == 'edinburgh':
            time.sleep(10800)

        # For every fetched ride 
        for ride in res_json:
            # If 'last_modification' field exists and trip offers a ride
            if ride['last_modification'] != '' and ride['driver']['state'] != 0:
                # Compute ride date and flexibility
                if ride['outward']['mintime'] != None and ride['outward']['maxtime'] != None:
                    flexibility = int((time_to_sec(ride['outward']['maxtime']) - time_to_sec(ride['outward']['mintime'])) / 2)
                else:
                    flexibility = 0
                ride_date = date_to_sec(ride['outward']['mindate'], "%Y-%m-%d") + time_to_sec(ride['outward']['mintime']) + flexibility
                # Compute return ride date and flexibility
                if 'return' in ride and ride['return'] != None and ride['return']['mindate'] != None and ride['return']['mintime'] != None:
                    if ride['return']['mintime'] != None and ride['return']['maxtime'] != None:
                        return_flexibility = int((time_to_sec(ride['return']['maxtime']) - time_to_sec(ride['return']['mintime'])) / 2)
                    else:
                        return_flexibility = 0
                    return_ride_date = date_to_sec(ride['return']['mindate'], "%Y-%m-%d") + time_to_sec(ride['return']['mintime']) + return_flexibility
                else:
                    return_ride_date = None
                    return_flexibility = 0
                # Store ride date in UTC according to local time offset of each site
                if city == 'brussels':
                    ride_date = ride_date - 3600
                    return_ride_date = return_ride_date - 3600 if return_ride_date else None
                    last_modification = date_to_sec(ride['last_modification'], "%Y-%m-%d %H:%M:%S") - 3600
                elif city == 'edinburgh':
                    ride_date = ride_date
                    return_ride_date = return_ride_date if return_ride_date else None
                    last_modification = date_to_sec(ride['last_modification'], "%d/%m/%Y %H:%M:%S")
                elif city == 'ljubljana':
                    ride_date = ride_date - 3600
                    return_ride_date = return_ride_date - 3600 if return_ride_date else None
                    last_modification = date_to_sec(ride['last_modification'], "%Y-%m-%d %H:%M") - 3600
                elif city == 'ticino':
                    ride_date = ride_date - 3600
                    return_ride_date = return_ride_date - 3600 if return_ride_date else None
                    last_modification = date_to_sec(ride['last_modification'], "%d/%m/%Y %H:%M:%S") - 3600
                # If city is Brussels
                if city == 'brussels':
                    # Don't add past rides into DB
                    if timestamp < ride_date:
                        site = sites_collection.find_one({'name': 'Brussels'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = float(ride['from']['latitude'].replace(",", "."))
                        s_lon = float(ride['from']['longitude'].replace(",", "."))
                        t_lat = float(ride['to']['latitude'].replace(",", "."))
                        t_lon = float(ride['to']['longitude'].replace(",", "."))

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(ride['uuid'], 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > ride_date:
                                # Fetch ride with uuid from database
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': brussels_driver_id,
                                        'car_id': brussels_car_id,
                                        'name': '%s - %s' % (ride['from']['address'], ride['to']['address']),
                                        'start_point': {
                                            'lat': float(ride['from']['latitude'].replace(",", ".")),
                                            'lon': float(ride['from']['longitude'].replace(",", "."))
                                        },
                                        'end_point': {
                                            'lat': float(ride['to']['latitude'].replace(",", ".")),
                                            'lon': float(ride['to']['longitude'].replace(",", "."))
                                        },
                                        'date': ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': ride['url']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != ride_date:
                                        ride_data = {
                                            'driver_id': brussels_driver_id,
                                            'car_id': brussels_car_id,
                                            'name': '%s - %s' % (ride['from']['address'], ride['to']['address']),
                                            'start_point': {
                                                'lat': float(ride['from']['latitude'].replace(",", ".")),
                                                'lon': float(ride['from']['longitude'].replace(",", "."))
                                            },
                                            'end_point': {
                                                'lat': float(ride['to']['latitude'].replace(",", ".")),
                                                'lon': float(ride['to']['longitude'].replace(",", "."))
                                            },
                                            'date': ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': ride['url']
                                            }
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                    # Don't add past rides into DB
                    if return_ride_date and timestamp < return_ride_date:
                        site = sites_collection.find_one({'name': 'Brussels'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = float(ride['from']['latitude'].replace(",", "."))
                        s_lon = float(ride['from']['longitude'].replace(",", "."))
                        t_lat = float(ride['to']['latitude'].replace(",", "."))
                        t_lon = float(ride['to']['longitude'].replace(",", "."))

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid('%sret' % ride['uuid'], 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > return_ride_date:
                                # Fetch ride with uuid from database
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': brussels_driver_id,
                                        'car_id': brussels_car_id,
                                        'name': '%s - %s' % (ride['to']['address'], ride['from']['address']),
                                        'start_point': {
                                            'lat': float(ride['to']['latitude'].replace(",", ".")),
                                            'lon': float(ride['to']['longitude'].replace(",", "."))
                                        },
                                        'end_point': {
                                            'lat': float(ride['from']['latitude'].replace(",", ".")),
                                            'lon': float(ride['from']['longitude'].replace(",", "."))
                                        },
                                        'date': return_ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': ride['url']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != return_ride_date:
                                        ride_data = {
                                            'driver_id': brussels_driver_id,
                                            'car_id': brussels_car_id,
                                            'name': '%s - %s' % (ride['to']['address'], ride['from']['address']),
                                            'start_point': {
                                                'lat': float(ride['to']['latitude'].replace(",", ".")),
                                                'lon': float(ride['to']['longitude'].replace(",", "."))
                                            },
                                            'end_point': {
                                                'lat': float(ride['from']['latitude'].replace(",", ".")),
                                                'lon': float(ride['from']['longitude'].replace(",", "."))
                                            },
                                            'date': return_ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': 'https://www.carpool.be/cplz/%s' % (ride['uuid']) # TODO: Probably a different URL for Brussels
                                            }
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                # If city is Edinburgh
                elif city == 'edinburgh':
                    # Don't add past rides into DB
                    if timestamp < ride_date:
                        site = sites_collection.find_one({'name': 'Edinburgh'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(ride['uuid'], 24)

                            # If uuid already exists in ids_to_keep then generate a new uuid based on ride date and insert it in ids_to_keep
                            if uuid in ids_to_keep:
                                uuid = generate_custom_objectid('%s%s' % (ride['uuid'], ride_date), 24)

                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': edinburgh_driver_id,
                                        'car_id': edinburgh_car_id,
                                        'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                        'start_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'date': ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': 'https://liftshare.com/uk/lift/view/%s?community=iip' % (ride['uuid'])
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != ride_date:
                                        ride_data = {
                                            'driver_id': edinburgh_driver_id,
                                            'car_id': edinburgh_car_id,
                                            'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                            'start_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'date': ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': 'https://liftshare.com/uk/lift/view/%s?community=iip' % (ride['uuid'])
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                    # Don't add past rides into DB
                    if return_ride_date and timestamp < return_ride_date:
                        site = sites_collection.find_one({'name': 'Edinburgh'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid('%sret' % ride['uuid'], 24)
                            
                            # If uuid already exists in ids_to_keep then generate a new uuid based on ride date and insert it in ids_to_keep
                            if uuid in ids_to_keep:
                                uuid = generate_custom_objectid('%sret%s' % (ride['uuid'], return_ride_date), 24)
                            
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > return_ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': edinburgh_driver_id,
                                        'car_id': edinburgh_car_id,
                                        'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                        'start_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'date': return_ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': 'https://liftshare.com/uk/lift/view/%s?community=iip' % (ride['uuid'])
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != return_ride_date:
                                        ride_data = {
                                            'driver_id': edinburgh_driver_id,
                                            'car_id': edinburgh_car_id,
                                            'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                            'start_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'date': return_ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': 'https://liftshare.com/uk/lift/view/%s?community=iip' % (ride['uuid'])
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                # If city is Ljubljana
                elif city == 'ljubljana':
                    # Don't add past rides into DB
                    if timestamp < ride_date:
                        site = sites_collection.find_one({'name': 'Ljubljana'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(str(ride['uuid']), 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': ljubljana_driver_id,
                                        'car_id': ljubljana_car_id,
                                        'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                        'start_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'date': ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': ride['public_uri']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != ride_date:
                                        ride_data = {
                                            'driver_id': ljubljana_driver_id,
                                            'car_id': ljubljana_car_id,
                                            'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                            'start_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'date': ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': ride['public_uri']
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                    # Don't add past rides into DB
                    if return_ride_date and timestamp < return_ride_date:
                        site = sites_collection.find_one({'name': 'Ljubljana'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(str('%sret' % ride['uuid']), 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > return_ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': ljubljana_driver_id,
                                        'car_id': ljubljana_car_id,
                                        'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                        'start_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'date': return_ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': ride['public_uri']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != return_ride_date:
                                        ride_data = {
                                            'driver_id': ljubljana_driver_id,
                                            'car_id': ljubljana_car_id,
                                            'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                            'start_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'date': return_ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': ride['public_uri']
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                # If city is Ticino
                elif city == 'ticino':
                    # Don't add past rides into DB
                    if timestamp < ride_date:
                        site = sites_collection.find_one({'name': 'Canton Ticino'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(str(ride['uuid']), 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': ticino1_driver_id,
                                        'car_id': ticino1_car_id,
                                        'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                        'start_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'date': ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url': ride['url']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != ride_date:
                                        ride_data = {
                                            'driver_id': ticino1_driver_id,
                                            'car_id': ticino1_car_id,
                                            'name': '%s - %s' % (ride['from']['city'], ride['to']['city']),
                                            'start_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'date': ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': ride['url']
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
                    # Don't add past rides into DB
                    if return_ride_date and timestamp < return_ride_date:
                        site = sites_collection.find_one({'name': 'Canton Ticino'})

                        bb_minlat = site['bounding_box']['min_lat']
                        bb_minlon = site['bounding_box']['min_lon']
                        bb_maxlat = site['bounding_box']['max_lat']
                        bb_maxlon = site['bounding_box']['max_lon']
                        s_lat = ride['from']['latitude']
                        s_lon = ride['from']['longitude']
                        t_lat = ride['to']['latitude']
                        t_lon = ride['to']['longitude']

                        # Don't add rides that are outside bounding box into DB
                        if inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, s_lat, s_lon, t_lat, t_lon):
                            uuid = generate_custom_objectid(str('%sret' % ride['uuid']), 24)
                            ids_to_keep.append(uuid)

                            # Don't add rides that exceed period time into DB
                            if timestamp + (period * 3600) > return_ride_date:
                                # Fetch ride with uuid from database 
                                cursor_rides = rides_collection.find({ '_id': str_to_oid(uuid) })

                                # If ride not in database POST
                                if cursor_rides.count() == 0:
                                    ride_data = {
                                        '_id': uuid,
                                        'driver_id': ticino1_driver_id,
                                        'car_id': ticino1_car_id,
                                        'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                        'start_point': {
                                            'lat': ride['to']['latitude'],
                                            'lon': ride['to']['longitude']
                                        },
                                        'end_point': {
                                            'lat': ride['from']['latitude'],
                                            'lon': ride['from']['longitude']
                                        },
                                        'date': return_ride_date,
                                        'activated': True,
                                        'polyline': waypoints_to_polyline(ride['waypoints']),
                                        'extras': {
                                            'uuid': ride['uuid'],
                                            'url':ride['url']
                                        },
                                    }
                                    rides.append(ride_data)
                                # If ride in database PATCH
                                else:
                                    # Store fetched ride
                                    for f_ride in cursor_rides:
                                        fetched_ride = f_ride
                                    # If a ride is modified between the intervals
                                    if (timestamp - last_modification) < interval or fetched_ride['date'] != return_ride_date:
                                        ride_data = {
                                            'driver_id': ticino1_driver_id,
                                            'car_id': ticino1_car_id,
                                            'name': '%s - %s' % (ride['to']['city'], ride['from']['city']),
                                            'start_point': {
                                                'lat': ride['to']['latitude'],
                                                'lon': ride['to']['longitude']
                                            },
                                            'end_point': {
                                                'lat': ride['from']['latitude'],
                                                'lon': ride['from']['longitude']
                                            },
                                            'date': return_ride_date,
                                            'polyline': waypoints_to_polyline(ride['waypoints']),
                                            'extras': {
                                                'uuid': ride['uuid'],
                                                'url': ride['url']
                                            },
                                        }

                                        json_body = json.dumps(ride_data)
                                        patch_rides_url = "%s://%s:%s/rest/v2/rides/%s" % (prefix, host, port, uuid)
                                        patch_res = requests.patch(patch_rides_url, data=json_body, headers=headers, auth=auth)

                                        if patch_res.status_code == 200:
                                            counter = counter + 1
        # If rides to POST                         
        if len(rides) > 0:
            json_body = json.dumps(rides)
            post_rides_url = "%s://%s:%s/rest/v2/rides" % (prefix, host, port)
            post_res = requests.post(post_rides_url, data=json_body, headers=headers, auth=auth)
            if post_res.status_code == 201:
                # print("%s | %s - %s" % (post_res.status_code, post_res.url, post_res.text))
                print('    %s rides added to database' % (len(rides)))
            else:
                print('    Error when posting rides into database')
        if counter > 0:
            print('    %s rides updated in database' % (counter))
    else:
        print("%s - %s" % (r.status_code, r.text))

    #-----------------------------------------------------------------------
    # Delete obsolete rides
    #-----------------------------------------------------------------------
    if city == 'brussels':
        city_regex = 'carpool.be'
        site_name = 'Brussels'
    elif city == 'edinburgh':
        city_regex = 'liftshare.com'
        site_name = 'Edinburgh'
    elif city == 'ljubljana':
        city_regex = 'prevoz.org'
        site_name = 'Ljubljana'
    elif city == 'ticino':
        city_regex = 'bepooler.ch'
        site_name = 'Canton Ticino'

    rides_url = "%s://%s:%s/rest/v2/rides" % (prefix, host, port)
    # Fetch all rides from database
    cursor_rides = rides_collection.find({ '$and': [ {'_deleted': {'$eq': False}}, {'extras.url': { '$regex': city_regex}} ] })

    # For every ride
    for ride in cursor_rides:
        if oid_to_str(ride['_id']) not in ids_to_keep:
            # DELETE rides if they are not included in API
            delete_rides_url = '%s/%s' % (rides_url, ride['_id'])
            delete_res_rides = requests.delete(delete_rides_url, headers=headers, auth=auth)
            if delete_res_rides.status_code == 204:
                counter_api = counter_api + 1
    if counter_api > 0:
        print('    -------------------------------------------------------')
        print('    %s obsolete rides deleted from database' % counter_api)

    # Update nightly_version field
    site = sites_collection.find_one({'name': site_name})
    site['carpooling_info']['nightly_version'] = site['carpooling_info']['nightly_version'] + 1
    site['carpooling_info']['nightly_updated'] = int(time.time())
    sites_collection.update({'_id': site['_id']}, site, upsert = False)

#===============================================================================
# addDriverAndCar ()
#===============================================================================
def addDriverAndCar(host, port, use_ssl):

    prefix = "https" if use_ssl else "http"

    auth = HTTPBasicAuth('admin', 'password') # TODO: Insert admin credentials here
    headers = {'content-type': 'application/json'}

    #===============================================================================
    # GET or POST dummy driver for Brussels
    #===============================================================================
    user_data = {
        "email": "brussels@rdex.com",
        "password": "password",
        "name": "Carpool.be driver",
        "phone": "n/a",
        "dob": "1970-12-31",
        "gender": "MALE",
        "fcm_token": "1234567890"
    }
    json_body = json.dumps(user_data)

    get_user_url = "%s://%s:%s/rest/v2/users?email=%s" % (prefix, host, port, user_data['email'])
    get_res = requests.get(get_user_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global brussels_driver_id
        if get_res_json['users']:
            # user exists
            brussels_driver_id = get_res_json['users'][0]['_id']
        else:
            # post user
            post_user_url = "%s://%s:%s/rest/v2/users" % (prefix, host, port)
            post_res = requests.post(post_user_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            brussels_driver_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy car for Brussels
    #===============================================================================
    car_data = {
        "owner_id": brussels_driver_id,
        "model": "Carpool.be car",
        "plate": "carpool.be",
        "colour": "black",
        "seats": 4,
        "car_usage_preferences": {
            "air_conditioning": False,
            "child_seat": False,
            "food_allowed": False,
            "luggage_type": "SMALL",
            "pets_allowed": False,
            "smoking_allowed": False,
            "music_allowed": False
        }
    }
    json_body = json.dumps(car_data)

    get_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
    get_res = requests.get(get_car_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global brussels_car_id
        for car in get_res_json['cars']:
            if car['owner_id'] == brussels_driver_id:
                # car exists
                brussels_car_id = car['_id']

        if brussels_car_id == None:
            # POST car
            post_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
            post_res = requests.post(post_car_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            brussels_car_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy driver for Edinburgh
    #===============================================================================
    user_data = {
        "email": "edinburgh@rdex.com",
        "password": "password",
        "name": "Liftshare driver",
        "phone": "n/a",
        "dob": "1970-12-31",
        "gender": "MALE",
        "fcm_token": "1234567890"
    }
    json_body = json.dumps(user_data)

    get_user_url = "%s://%s:%s/rest/v2/users?email=%s" % (prefix, host, port, user_data['email'])
    get_res = requests.get(get_user_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global edinburgh_driver_id
        if get_res_json['users']:
            # user exists
            edinburgh_driver_id = get_res_json['users'][0]['_id']
        else:
            # post user
            post_user_url = "%s://%s:%s/rest/v2/users" % (prefix, host, port)
            post_res = requests.post(post_user_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            edinburgh_driver_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy car for Edinburgh
    #===============================================================================
    car_data = {
        "owner_id": edinburgh_driver_id,
        "model": "Liftshare car",
        "plate": "liftshare",
        "colour": "black",
        "seats": 4,
        "car_usage_preferences": {
            "air_conditioning": False,
            "child_seat": False,
            "food_allowed": False,
            "luggage_type": "SMALL",
            "pets_allowed": False,
            "smoking_allowed": False,
            "music_allowed": False
        }
    }
    json_body = json.dumps(car_data)

    get_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
    get_res = requests.get(get_car_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global edinburgh_car_id
        for car in get_res_json['cars']:
            if car['owner_id'] == edinburgh_driver_id:
                # car exists
                edinburgh_car_id = car['_id']

        if edinburgh_car_id == None:
            # POST car
            post_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
            post_res = requests.post(post_car_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            edinburgh_car_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy driver for Ljubljana
    #===============================================================================
    user_data = {
        "email": "ljubljana@rdex.com",
        "password": "password",
        "name": "Prevoz driver",
        "phone": "n/a",
        "dob": "1970-12-31",
        "gender": "MALE",
        "fcm_token": "1234567890"
    }
    json_body = json.dumps(user_data)

    get_user_url = "%s://%s:%s/rest/v2/users?email=%s" % (prefix, host, port, user_data['email'])
    get_res = requests.get(get_user_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ljubljana_driver_id
        if get_res_json['users']:
            # user exists
            ljubljana_driver_id = get_res_json['users'][0]['_id']
        else:
            # post user
            post_user_url = "%s://%s:%s/rest/v2/users" % (prefix, host, port)
            post_res = requests.post(post_user_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ljubljana_driver_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy car for Ljubljana
    #===============================================================================
    car_data = {
        "owner_id": ljubljana_driver_id,
        "model": "Prevoz car",
        "plate": "prevoz",
        "colour": "black",
        "seats": 4,
        "car_usage_preferences": {
            "air_conditioning": False,
            "child_seat": False,
            "food_allowed": False,
            "luggage_type": "SMALL",
            "pets_allowed": False,
            "smoking_allowed": False,
            "music_allowed": False
        }
    }
    json_body = json.dumps(car_data)

    get_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
    get_res = requests.get(get_car_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ljubljana_car_id
        for car in get_res_json['cars']:
            if car['owner_id'] == ljubljana_driver_id:
                # car exists
                ljubljana_car_id = car['_id']

        if ljubljana_car_id == None:
            # POST car
            post_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
            post_res = requests.post(post_car_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ljubljana_car_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy driver for Ticino 1
    #===============================================================================
    user_data = {
        "email": "ticino1@rdex.com",
        "password": "password",
        "name": "Bepooler driver",
        "phone": "n/a",
        "dob": "1970-12-31",
        "gender": "MALE",
        "fcm_token": "1234567890"
    }
    json_body = json.dumps(user_data)

    get_user_url = "%s://%s:%s/rest/v2/users?email=%s" % (prefix, host, port, user_data['email'])
    get_res = requests.get(get_user_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ticino1_driver_id
        if get_res_json['users']:
            # user exists
            ticino1_driver_id = get_res_json['users'][0]['_id']
        else:
            # post user
            post_user_url = "%s://%s:%s/rest/v2/users" % (prefix, host, port)
            post_res = requests.post(post_user_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ticino1_driver_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy car for Ticino 1
    #===============================================================================
    car_data = {
        "owner_id": ticino1_driver_id,
        "model": "Bepooler car",
        "plate": "bepooler",
        "colour": "black",
        "seats": 4,
        "car_usage_preferences": {
            "air_conditioning": False,
            "child_seat": False,
            "food_allowed": False,
            "luggage_type": "SMALL",
            "pets_allowed": False,
            "smoking_allowed": False,
            "music_allowed": False
        }
    }
    json_body = json.dumps(car_data)

    get_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
    get_res = requests.get(get_car_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ticino1_car_id
        for car in get_res_json['cars']:
            if car['owner_id'] == ticino1_driver_id:
                # car exists
                ticino1_car_id = car['_id']

        if ticino1_car_id == None:
            # POST car
            post_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
            post_res = requests.post(post_car_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ticino1_car_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy driver for Ticino 2
    #===============================================================================
    user_data = {
        "email": "ticino2@rdex.com",
        "password": "password",
        "name": "Mobalt driver",
        "phone": "n/a",
        "dob": "1970-12-31",
        "gender": "MALE",
        "fcm_token": "1234567890"
    }
    json_body = json.dumps(user_data)

    get_user_url = "%s://%s:%s/rest/v2/users?email=%s" % (prefix, host, port, user_data['email'])
    get_res = requests.get(get_user_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ticino2_driver_id
        if get_res_json['users']:
            # user exists
            ticino2_driver_id = get_res_json['users'][0]['_id']
        else:
            # post user
            post_user_url = "%s://%s:%s/rest/v2/users" % (prefix, host, port)
            post_res = requests.post(post_user_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ticino2_driver_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

    #===============================================================================
    # GET or POST dummy car for Ticino 2
    #===============================================================================
    car_data = {
        "owner_id": ticino2_driver_id,
        "model": "Mobalt car",
        "plate": "mobalt",
        "colour": "black",
        "seats": 4,
        "car_usage_preferences": {
            "air_conditioning": False,
            "child_seat": False,
            "food_allowed": False,
            "luggage_type": "SMALL",
            "pets_allowed": False,
            "smoking_allowed": False,
            "music_allowed": False
        }
    }
    json_body = json.dumps(car_data)

    get_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
    get_res = requests.get(get_car_url, headers=headers, auth=auth)
    get_res_json = json.loads(get_res.text)

    try:
        global ticino2_car_id
        for car in get_res_json['cars']:
            if car['owner_id'] == ticino2_driver_id:
                # car exists
                ticino2_car_id = car['_id']

        if ticino2_car_id == None:
            # POST car
            post_car_url = "%s://%s:%s/rest/v2/cars" % (prefix, host, port)
            post_res = requests.post(post_car_url, data=json_body, headers=headers, auth=auth)
            post_res_json = json.loads(post_res.text)
            ticino2_car_id = post_res_json['_id']
    except KeyError:
        print("%s | %s - %s" % (get_res.status_code, get_res.url, get_res.text))

#===============================================================================
# run_periodically ()
#===============================================================================
def run_periodically(host, port, interval, period, radius, dbname, city, use_ssl):
    # This implementation is subject to change
    threading.Timer(interval, run_periodically, args=(host, port, interval, period, radius, dbname, city, use_ssl)).start()
    periodic_pull(host, port, interval, period, radius, dbname, city, use_ssl)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('h', metavar='HOST', help="Server HOST (e.g. 'localhost')", type=str)
    parser.add_argument('p', metavar='PORT', help="Server PORT (e.g. '5000')", type=str)
    parser.add_argument('-i', '--interval', metavar='INTERVAL', help="Interval to run this script periodically (secs)", type=int, default=60)
    parser.add_argument('-r', '--period', metavar='PERIOD', help="Retrieve all rides within a certain period (max 72 hours)", type=int, default=12)
    parser.add_argument('-d', '--radius', metavar='RADIUS', help="Retrieve all rides within a certain radius", type=int, default=20)
    parser.add_argument('dbname', metavar='DBNAME', help="Database name", type=str)
    parser.add_argument('city', metavar='CITY', help='City name - currently: ' + ', '.join(CITIES), choices=CITIES, type=str)
    parser.add_argument('--ssl', help="Use SSL", action='store_true', default=False)
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
    period = args.period
    radius = args.radius
    city = args.city
    host = args.h
    port = args.p
    use_ssl = args.ssl

    print('city:      %s' % (city))
    print('interval:      %s' % (interval))
    print('period:      %s' % (period))
    print('radius:      %s' % (radius))
    print(' * RDEX Periodic Pull Service is active! * ')

    addDriverAndCar(host, port, use_ssl)
    run_periodically(host, port, interval, period, radius, dbname, city, use_ssl)

if __name__ == '__main__':
    main()
