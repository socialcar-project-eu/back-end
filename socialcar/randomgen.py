# -*- coding: utf-8 -*-
import random
import time
from bson import ObjectId

# Random trips generation
NUM_TRIPS_MIN = 0
NUM_TRIPS_MAX = 3
NUM_STEPS_MIN = 1
NUM_STEPS_MAX = 5
STEP_DURATION_MIN =  5 * 60  # 5 minutes
STEP_DURATION_MAX = 20 * 60
STEP_WAIT_TIME_MIN =  5 * 60
STEP_WAIT_TIME_MAX = 20 * 60
LAT_MIN = 40
LAT_MAX = 42
LON_MIN = 11
LON_MAX = 13
LAT_LON_DECIMAL_POINTS = 6
ROADS = [ 'Boswell Rd', 'Pall Mall', 'Upsall Grove', 'Beechfield Rd', 'Glan Dafarn' ]
ADDRESS_NUM_MAX = 200
STOPS = [ 'FLAMINIA NUOVA', 'CASAL SELCE', 'OCEANO INDIANO' ]
TRANSPORT_NUM_MAX = 999
PRICE_MAX = 10
PRICE_DECIMAL_POINTS = 2

# Random positions generation
NUM_USERS_POSITION_MIN = 0.8  # random positions for at least 80% of users
NUM_POSITIONS_PER_USER_MIN = 0
NUM_POSITIONS_PER_USER_MAX = 10
POSITIONS_MIN_TIMESTAMP = 1451606400        # from 1/1/2016
POSITIONS_MAX_TIMESTAMP = int(time.time())  # to now

#===============================================================================
# objectids_to_str ()
#===============================================================================
def objectids_to_str(obj):
    assert isinstance(obj, list) or isinstance(obj, dict)
    obj_list = obj if isinstance(obj, list) else [ obj ]
    for i in range(len(obj_list)):
        if isinstance(obj_list[i], ObjectId):
            obj_list[i] = str(obj_list[i])
        elif isinstance(obj_list[i], list):
            objectids_to_str(obj_list[i])
        elif isinstance(obj_list[i], dict):
            d = obj_list[i]
            for key in d:
                if isinstance(d[key], ObjectId):
                    d[key] = str(d[key])
                elif isinstance(d[key], list) or isinstance(d[key], dict):
                    objectids_to_str(d[key])

            # Remove eve extra fields
            for key in list(d):  # list(): get copy of keys (we modify dict)
                if key.startswith('_') and key != '_id':
                    d.pop(key)

#===============================================================================
# get_real_objectids ()
#===============================================================================
def get_real_objectids(db):
    resources = [ 'users', 'cars', 'rides' ]
    d = {}
    for resource in resources:
        d[resource] = [ v for v in db[resource].find({'_deleted': False}) ]
        assert d[resource]
        objectids_to_str(d[resource])
    return d

#===============================================================================
# random_trips ()
#===============================================================================
def random_trips(request, db):
    state = {}
    state['ids'] = get_real_objectids(db)
    num_trips = random.randint(NUM_TRIPS_MIN, NUM_TRIPS_MAX)
    return [ random_trip(request, state) for _ in range(num_trips) ]

#===============================================================================
# random_trip ()
#===============================================================================
def random_trip(request, state):
    state['used_car_pooling'] = False
    state['last_step_time'] = time.time() + 120 * 60  # 2 hours from now
    num_steps = random.randint(NUM_STEPS_MIN, NUM_STEPS_MAX)
    return {
        'steps': [ random_step(request, state) for _ in range(num_steps) ]
    }

#===============================================================================
# random_step ()
#===============================================================================
def random_step(request, state):
    return {
        'route': random_route(request, state),
        'transport': random_transport(request, state),
        'price': random_price(request, state),
        'distance': random_distance(request, state),
    }

#===============================================================================
# random_route ()
#===============================================================================
def random_route(request, state):
    start_timestamp = state['last_step_time'] + random.randint(STEP_WAIT_TIME_MIN, STEP_WAIT_TIME_MAX)
    end_timestamp = start_timestamp + random.randint(STEP_DURATION_MIN, STEP_DURATION_MAX)
    state['last_step_time'] = end_timestamp
    return {
        'start_point': {
            'point': {
                'lat': round(random.uniform(LAT_MIN, LAT_MAX), LAT_LON_DECIMAL_POINTS),
                'lon': round(random.uniform(LON_MIN, LON_MAX), LAT_LON_DECIMAL_POINTS),
            },
            'date': int(start_timestamp),
            'address': '%d %s' % (random.randint(1, ADDRESS_NUM_MAX), random.choice(ROADS))
        },
        'end_point': {
            'point': {
                'lat': round(random.uniform(LAT_MIN, LAT_MAX), LAT_LON_DECIMAL_POINTS),
                'lon': round(random.uniform(LON_MIN, LON_MAX), LAT_LON_DECIMAL_POINTS),
            },
            'date': int(end_timestamp),
            'address': '%d %s' % (random.randint(1, ADDRESS_NUM_MAX), random.choice(ROADS))
        }
    }

#===============================================================================
# random_transport ()
#===============================================================================
def random_transport(request, state):
    travel_modes = [ 'CAR_POOLING', 'METRO', 'BUS', 'RAIL', 'FEET', 'TRAM' ]
    d = state['ids']
    if request:
        if request.args['use_bus'] == 'false':
            travel_modes.remove('BUS')
        if request.args['use_metro'] == 'false':
            travel_modes.remove('METRO')
        if request.args['use_train'] == 'false':
            travel_modes.remove('RAIL')

    # For now, allow only one car pooling step per trip
    if state['used_car_pooling']:
        travel_modes.remove('CAR_POOLING')

    travel_mode = random.choice(travel_modes)
    if travel_mode in [ 'METRO', 'BUS', 'RAIL', 'FEET', 'TRAM' ]:
        num = random.randint(1, TRANSPORT_NUM_MAX)
        stop = random.choice(STOPS)
        return {
            'travel_mode': travel_mode,
            'short_name': '%s' % num,
            'long_name': '%s towards %s' % (num, stop)
        }
    elif travel_mode == 'CAR_POOLING':
        state['used_car_pooling'] = True
        ride = random.choice(d['rides'])
        return {
            'travel_mode': 'CAR_POOLING',
            'ride_id': ride['_id'],
            'car_id': ride['car_id'],
            'driver_id': ride['driver_id'],
        }

#===============================================================================
# random_price ()
#===============================================================================
def random_price(request, state):
    return {
        'amount': round(random.uniform(1, PRICE_MAX), PRICE_DECIMAL_POINTS),
        'currency': 'EUR'
    }

#===============================================================================
# random_distance ()
#===============================================================================
def random_distance(request, state):
    return random.randint(1, 10)

#===============================================================================
# random_positions ()
#===============================================================================
def random_positions(request, db):
    state = {}
    state['ids'] = get_real_objectids(db)
    state['user_created'] = 0
    num_users = int(len(state['ids']['users']) * random.uniform(NUM_USERS_POSITION_MIN, 1))
    return [ random_user_positions(request, state) for _ in range(num_users) ]

#===============================================================================
# random_user_positions ()
#===============================================================================
def random_user_positions(request, state):
    num_positions = random.randint(NUM_POSITIONS_PER_USER_MIN, NUM_POSITIONS_PER_USER_MAX)
    user_positions = {
        'user_id': state['ids']['users'][state['user_created']]['_id'],
        'positions': [ random_position(request, state) for _ in range(num_positions) ]
    }
    state['user_created'] += 1
    return user_positions

#===============================================================================
# random_position ()
#===============================================================================
def random_position(request, state):
    return {
        'point': {
            'lat': round(random.uniform(LAT_MIN, LAT_MAX), LAT_LON_DECIMAL_POINTS),
            'lon': round(random.uniform(LON_MIN, LON_MAX), LAT_LON_DECIMAL_POINTS),
        },
        'timestamp': random.randint(POSITIONS_MIN_TIMESTAMP, POSITIONS_MAX_TIMESTAMP)
    }