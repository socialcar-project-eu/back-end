import pymongo
import os
from socialcar.settings import MONGO_DBNAME

TABLE_OF_ZONES = [[1,1,3,1,1,2,3,2,2,1],
                  [1,1,2,1,1,2,3,2,2,1],
                  [3,2,1,3,3,3,3,3,3,3],
                  [1,1,3,1,1,2,2,2,2,1],
                  [1,1,3,1,1,2,3,2,2,1],
                  [2,2,3,2,2,1,3,2,2,2],
                  [3,3,3,2,3,3,1,3,3,3],
                  [2,2,3,2,2,2,3,1,2,2],
                  [2,2,3,2,2,2,3,2,1,2],
                  [1,1,3,1,1,2,3,2,2,1]]


MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_ZONE_ID_COLLECTION = 'citybus_zone'
BUS_STOP_ID = 'lpp_id'

#===============================================================================
# rail_fare ()
#===============================================================================
def rail_fare(distance, name):
    # convert meters to kilometers
    distance = float(distance)/1000
    # in case tariff per km is used as in .xlsx for Brussels
    if name == 'Brussels':
        if distance <= 8:
            return 2.20
        elif distance <= 9:
            return 2.30
        elif distance <= 10:
            return 2.40
        elif distance <= 11:
            return 2.60
        elif distance <= 12:
            return 2.70
        elif distance <= 13:
            return 2.80
        elif distance <= 14:
            return 3.00
        elif distance <= 15:
            return 3.10
        elif distance <= 16:
            return 3.20
        elif distance <= 17:
            return 3.40
        elif distance <= 18:
            return 3.50
        elif distance <= 19:
            return 3.70
        elif distance <= 20:
            return 3.80
        elif distance <= 21:
            return 3.90
        elif distance <= 22:
            return 4.10
        elif distance <= 23:
            return 4.20
        elif distance <= 24:
            return 4.40
        elif distance <= 25:
            return 4.50
        elif distance <= 26:
            return 4.60
        elif distance <= 27:
            return 4.80
        elif distance <= 28:
            return 4.90
        elif distance <= 29:
            return 5.10
        elif distance <= 30:
            return 5.20
        elif distance <= 33:
            return 5.50
        elif distance <= 36:
            return 5.90
        elif distance <= 39:
            return 6.30
        elif distance <= 42:
            return 6.70
        elif distance <= 45:
            return 7.10
        elif distance <= 48:
            return 7.60
        elif distance <= 51:
            return 8.00
        elif distance <= 54:
            return 8.40
        elif distance <= 57:
            return 8.80
        elif distance <= 60:
            return 9.20
        elif distance <= 65:
            return 9.80
        elif distance <= 70:
            return 10.50
        elif distance <= 75:
            return 11.20
        elif distance <= 80:
            return 11.90
        elif distance <= 85:
            return 12.60
        elif distance <= 90:
            return 13.30
        elif distance <= 95:
            return 14.00
        elif distance <= 100:
            return 14.70
        elif distance <= 105:
            return 15.30
        elif distance <= 110:
            return 16.00
        elif distance <= 115:
            return 16.70
        elif distance <= 120:
            return 17.40
        elif distance <= 125:
            return 18.10
        elif distance <= 130:
            return 18.80
        elif distance <= 135:
            return 19.50
        elif distance <= 140:
            return 20.20
        elif distance <= 145:
            return 20.90
        else:
            return 21.90
    # in case tariff per km is used instead of City - Rail Ljubljana (2.2 EUR fare) as in .xlsx for Ljubljana
    elif name == 'Ljubljana':
        if distance <= 10:
            return 1.28
        elif distance <= 20:
            return 1.85
        elif distance <= 30:
            return 2.58
        elif distance <= 40:
            return 3.44
        elif distance <= 50:
            return 4.28
        elif distance <= 60:
            return 5.08
        elif distance <= 70:
            return 5.80
        elif distance <= 80:
            return 6.59
        elif distance <= 90:
            return 6.99
        elif distance <= 100:
            return 7.17
        elif distance <= 120:
            return 7.70
        elif distance <= 140:
            return 8.49
        elif distance <= 160:
            return 9.56
        elif distance <= 180:
            return 10.91
        elif distance <= 200:
            return 12.02
        elif distance <= 220:
            return 12.95
        elif distance <= 240:
            return 13.99
        elif distance <= 260:
            return 14.77
        elif distance <= 280:
            return 15.81
        elif distance <= 300:
            return 16.68
        elif distance <= 320:
            return 17.67
        elif distance <= 340:
            return 18.58
        elif distance <= 360:
            return 19.50
        elif distance <= 380:
            return 20.54
        elif distance <= 400:
            return 21.59
        elif distance <= 420:
            return 22.37
        elif distance <= 440:
            return 23.29
        elif distance <= 460:
            return 24.34
        elif distance <= 480:
            return 25.24
        elif distance <= 500:
            return 26.44
        elif distance <= 525:
            return 27.47
        elif distance <= 550:
            return 28.67
        elif distance <= 575:
            return 30.10
        else:
            return 31.29
    else:
        return -1

#===============================================================================
# bus_fare ()
#===============================================================================
def bus_fare(leg, name):
    if name == 'Brussels':
        # If provider is TEC
        if leg['transport']['agency_id'] == 'TEC':
            return 3.50
        # If provider is De Lijn
        else:
            return 3.00
    elif name == 'Ljubljana':
        # from 'agency_id'  find type of bus (citybus or intercity), e.g for citybus:'lpp_2197', intercity: '2206108040402'
        if leg['transport']['agency_id'] == 'lpp':
            return citybus_ljubljana(leg['route']['points'][0]['stop_id'], leg['route']['points'][-1]['stop_id'], leg['distance'])
        else:
            return bus_intercity_ljubljana(leg['distance'])
    elif name == 'Canton Ticino':
        return 2.20 # ??how to calculate fare for 13 zones??
    else:
        return -1

#===============================================================================
# citybus_ljubljana ()
#===============================================================================
def citybus_ljubljana(start_id, end_id, distance):
    # have a collection in db with stop_id, zone_id to find the zone each bus stop belongs to (e.g db collection citybus_zone)
    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[MONGO_DBNAME]
    collection = db[MONGO_ZONE_ID_COLLECTION] # name of collection in db for stop_id --> zone_id mapping
    # find zone_id for first and last bus stops
    start = collection.find_one({BUS_STOP_ID: start_id})
    end = collection.find_one({BUS_STOP_ID: end_id})
    # from TABLE_OF_ZONES find the number of zones crossed
    if start['zone_id'] == 0 or end['zone_id'] == 0:
        # if 'zone_id' == 0 use intercity bus fare
        return bus_intercity_ljubljana(distance)
    else:
        number_of_zones = TABLE_OF_ZONES[start['zone_id']-1][end['zone_id']-1]

    if number_of_zones == 1:
        return 1.20
    elif number_of_zones == 2:
        return 1.60
    else:
        return 2.50

#===============================================================================
# bus_intercity_ljubljana ()
#===============================================================================
def bus_intercity_ljubljana(distance):
    # convert meters to kilometers
    distance = float(distance)/1000
    if distance <= 5:
        return 1.30
    elif distance <= 10:
        return 1.80
    elif distance <= 15:
        return 2.30
    elif distance <= 20:
        return 2.70
    elif distance <= 25:
        return 3.10
    elif distance <= 30:
        return 3.60
    elif distance <= 35:
        return 4.10
    elif distance <= 40:
        return 4.70
    elif distance <= 45:
        return 5.20
    elif distance <= 50:
        return 5.60
    elif distance <= 55:
        return 6.00
    elif distance <= 60:
        return 6.30
    elif distance <= 65:
        return 6.70
    elif distance <= 70:
        return 6.90
    elif distance <= 75:
        return 7.20
    elif distance <= 80:
        return 7.50
    elif distance <= 85:
        return 7.90
    elif distance <= 90:
        return 8.30
    elif distance <= 95:
        return 8.70
    elif distance <= 100:
        return 9.20
    elif distance <= 105:
        return 9.60
    elif distance <= 110:
        return 9.90
    elif distance <= 115:
        return 10.30
    elif distance <= 120:
        return 10.70
    elif distance <= 125:
        return 11.10
    elif distance <= 130:
        return 11.40
    elif distance <= 135:
        return 11.60
    elif distance <= 140:
        return 12.00
    elif distance <= 145:
        return 12.40
    elif distance <= 150:
        return 12.80
    elif distance <= 160:
        return 13.60
    elif distance <= 170:
        return 14.40
    elif distance <= 180:
        return 15.20
    elif distance <= 190:
        return 16.00
    elif distance <= 200:
        return 16.80
    elif distance <= 210:
        return 17.60
    elif distance <= 220:
        return 18.40
    elif distance <= 230:
        return 19.20
    elif distance <= 240:
        return 20.00
    elif distance <= 250:
        return 20.80
    elif distance <= 260:
        return 21.60
    elif distance <= 270:
        return 22.40
    elif distance <= 280:
        return 23.20
    elif distance <= 290:
        return 24.00
    elif distance <= 300:
        return 24.80
    elif distance <= 310:
        return 25.60
    elif distance <= 320:
        return 26.40
    elif distance <= 330:
        return 27.20
    elif distance <= 340:
        return 28.00
    elif distance <= 350:
        return 28.80
    elif distance <= 360:
        return 29.60
    else:
        return 30.40

#===============================================================================
# metro_fare ()
#===============================================================================
def metro_fare(name):
    if name == 'Brussels':
        return 2.10
    else:
        return -1

#===============================================================================
# tram_fare ()
#===============================================================================
def tram_fare(site, distance):
    return -1

#===============================================================================
# carpooling_fare ()
#===============================================================================
def carpooling_fare(distance, name):
    # convert meters to kilometers
    distance = float(distance)/1000
    if name == 'Edinburgh':
        # convert kms to miles
        distance = distance * 0.621
        limit = 30
        coefficient_one = 0.15
        coefficient_two = 0.07
    elif name == 'Brussels':
        limit = 100
        coefficient_one = 0.08
        coefficient_two = 0.04
    else:
        return -1

    if distance <= limit:
        return coefficient_one * distance
    else:
       return (coefficient_one * limit) + (distance - limit) * coefficient_two 

