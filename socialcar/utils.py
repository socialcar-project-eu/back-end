# -*- coding: utf-8 -*-
from __future__ import print_function
import json
import datetime
import polyline
import hashlib
import re
from bson import ObjectId
from math import radians, cos, sin, asin, sqrt

EARTH_RADIUS_KM = 6371.0

#===============================================================================
# str_to_json ()
#===============================================================================
def str_to_json(s):
    """
    Deserialize JSON formatted string 's' to a dict.

    Args:
        s: JSON string to be deserialized

    Examples:
    >>> str_to_json('{}')
    {}
    >>> str_to_json('{"a": 1, "c": {"d": 3}, "b": 2}') == {u'a': 1, u'c': {u'd': 3}, u'b': 2}
    True
    >>> str_to_json('a')
    Traceback (most recent call last):
        ...
    ValueError: No JSON object could be decoded
    """
    return json.loads(s.decode())

#===============================================================================
# json_to_str ()
#===============================================================================
def json_to_str(d):
    """
    Serialize dict 'd' to a JSON formatted string.

    Args:
        d: dictionary to be serialized
    Raises:
        TypeError: 'd' is not a list or dict

    Examples:
    >>> json_to_str({})
    '{}'
    >>> json_to_str({'a':1,'b':2,'c':{'d':3}})
    '{"a": 1, "c": {"d": 3}, "b": 2}'
    >>> json_to_str({1})
    Traceback (most recent call last):
        ...
    TypeError: Argument not a list or dict
    """
    if not isinstance(d, dict) and not isinstance(d, list):
        raise TypeError('Argument not a list or dict')
    return json.dumps(d)

#===============================================================================
# str_to_oid ()
#===============================================================================
def str_to_oid(s):
    """
    Deserialize string 's' to an ObjectId.

    Args:
        s: string to be deserialized
    Raises:
        TypeError: 's' is not an str or unicode

    Examples:
    >>> str_to_oid('582431a6a377f26970c543b3')
    ObjectId('582431a6a377f26970c543b3')
    >>> str_to_oid('582431a6a377f26970c543b')
    Traceback (most recent call last):
        ...
    InvalidId: '582431a6a377f26970c543b' is not a valid ObjectId, it must be a 12-byte input or a 24-character hex string
    """
    if not isinstance(s, str) and not isinstance(s, bytes):
        raise TypeError('Argument not an str or unicode')
    return ObjectId(s)

#===============================================================================
# oid_to_str ()
#===============================================================================
def oid_to_str(oid):
    """
    Serialize ObjectId 'oid' to string.

    Args:
        oid: ObjectId to be serialized
    Raises:
        TypeError: 'oid' is not an ObjectId

    Examples:
    >>> oid_to_str(ObjectId('582431a6a377f26970c543b3'))
    '582431a6a377f26970c543b3'
    >>> oid_to_str('582431a6a377f26970c543b3')
    Traceback (most recent call last):
        ...
    TypeError: Argument not an ObjectId
    """
    if not isinstance(oid, ObjectId):
        raise TypeError('Argument not an ObjectId')
    return str(oid)

#===============================================================================
# apply_function ()
#===============================================================================
def apply_function(obj, func, *args):
    """
    Apply function 'func' to object 'obj'. If 'obj' is a list, apply 'func'
    to all its elements. 'func' may optionally take some arguments 'args'.

    Returns:
        None

    Examples:
    >>> x = {'a':1, 'b': 2}
    >>> def zero(d):
    ...     for k in d:
    ...             d[k] = 0
    >>> apply_function(x, zero)
    >>> x == {'a': 0, 'b': 0}
    True
    >>> def inc(d, val):
    ...     for k in d:
    ...         d[k] += val
    >>> apply_function(x, inc, 4)
    >>> x == {'a': 4, 'b': 4}
    True
    >>> l = [ {'m': 1}, {'x': 2, 'y': 3} ]
    >>> apply_function(l, inc, 4)
    >>> l == [{'m': 5}, {'y': 7, 'x': 6}]
    True
    """
    for x in obj if isinstance(obj, list) else [ obj ]:
        func(x, *args)

#===============================================================================
# traverse_object ()
#===============================================================================
def traverse_object(obj, func, *args):
    """
    Recursivelly traverses all object fields and apply function 'func' (with
    optional arguments 'args') to each field.

    Args:
        obj: object to traverse. Must be a list or dict.
        func: function to apply to each object traversed.
    Returns:
        None
    Raises:
        TypeError: 'obj' is not a list or dict

    Examples:
    >>> def dict_set(obj, key, val):
    ...     if isinstance(obj, dict):
    ...         obj[key] = val
    >>> d = {'x': 1, 'b': 1, 'c': [ {'d': 1}, [ 'a', {'c': 1} ] ] }
    >>> traverse_object(d, dict_set, 'x', 4)
    >>> d == {'x': 4, 'b': 1, 'c': [ {'d': 1, 'x': 4}, ['a', {'c': 1, 'x': 4}]]}
    True
    """
    if not isinstance(obj, list) and not isinstance(obj, dict):
        raise TypeError('Argument not a list or dict')
    if not callable(func):
        raise TypeError('Argument not a function')

    func(obj, *args)

    if isinstance(obj, list):
        for x in obj:
            if isinstance(x, list) or isinstance(x, dict):
                traverse_object(x, func, *args)
    elif isinstance(obj, dict):
        for key in obj:
            if isinstance(obj[key], list) or isinstance(obj[key], dict):
                traverse_object(obj[key], func, *args)

#===============================================================================
# remove_fields ()
#===============================================================================
def remove_fields(d, fields):
    """
    Remove from dict 'd' all keys in list 'fields'.

    Args:
        d: a dict
        fields: list of keys to remove
    Returns:
        None

    Examples:
    >>> d = {'a': 1, 'b': 2, 'c': {'d': 3}}
    >>> remove_fields(d, ['a', 'd'])
    >>> d == {'b': 2, 'c': {'d': 3}}
    True
    """
    if isinstance(d, dict):
        for field in fields:
            d.pop(field, None)

#===============================================================================
# recursively_remove_fields ()
#===============================================================================
def recursively_remove_fields(obj, fields):
    """
    Remove from dict 'd' (and all embedded dicts) all keys in list 'fields'.

    Args:
        d: a dict
        fields: list of keys to remove
    Returns:
        None

    Examples:
    >>> d = {'a': 1, 'b': 2, 'c': {'d': 3}}
    >>> recursively_remove_fields(d, ['a', 'd'])
    >>> d == {'b': 2, 'c': {}}
    True
    """
    traverse_object(obj, remove_fields, fields)

#===============================================================================
# objectids_to_strings ()
#===============================================================================
def objectids_to_strings(obj):
    """
    Convert all fields and subfields of object 'obj' that are ObjectIds to str.

    Examples:
    >>> d = {'a': ObjectId('582431a6a377f26970c543b3'), 'b': {'d': [1, ObjectId('582431a6a377f26970c543b2')]}}
    >>> objectids_to_strings(d)
    >>> d == {'a': '582431a6a377f26970c543b3', 'b': {'d': [1, '582431a6a377f26970c543b2']}}
    True
    """
    def func(obj):
        if isinstance(obj, list):
            for i in range(len(obj)):
                if isinstance(obj[i], ObjectId):
                    obj[i] = oid_to_str(obj[i])
        elif isinstance(obj, dict):
            for key in obj:
                if isinstance(obj[key], ObjectId):
                    obj[key] = oid_to_str(obj[key])
    traverse_object(obj, func)

#===============================================================================
# strings_to_objectids ()
#===============================================================================
def strings_to_objectids(obj):
    """
    Convert all fields and subfields of object 'obj' that are valid objectid
    string to ObjectIds.

    Examples:
    >>> d = {'a': '582431a6a377f26970c543b3', 'b': {'d': [1, '582431a6a377f26970c543b2', '582431a6a377f26970c543b']}}
    >>> strings_to_objectids(d)
    >>> d == {'a': ObjectId('582431a6a377f26970c543b3'), 'b': {'d': [1, ObjectId('582431a6a377f26970c543b2'), '582431a6a377f26970c543b']}}
    True
    """
    def func(obj):
        if isinstance(obj, list):
            for i in range(len(obj)):
                if ObjectId.is_valid(obj[i]):
                    obj[i] = str_to_oid(obj[i])
        elif isinstance(obj, dict):
            for key in obj:
                if ObjectId.is_valid(obj[key]):
                    obj[key] = str_to_oid(obj[key])
    traverse_object(obj, func)

if __name__ == "__main__":
    import doctest
    res = doctest.testmod()
    print('%d/%d tests passed.' % (res.attempted - res.failed, res.attempted))

#===============================================================================
# km2rad ()
#===============================================================================
def km2rad(km):
    """
    Convert kilometers to radians.

    Examples:
    >>> km2rad(5)
    0.0007848061528802386
    """
    return float(km) / EARTH_RADIUS_KM

#===============================================================================
# rad2km ()
#===============================================================================
def rad2km(rad):
    """
    Convert radians to kilometers.

    Examples:
    >>> rad2km(5)
    31855.0
    """
    return float(rad) * EARTH_RADIUS_KM

#===============================================================================
# timestamp_to_date()
#===============================================================================
def timestamp_to_datetime(timestamp_str, date_format):
    """
    Convert unix timestamp to a specific date format.

    Examples:
    >>> timestamp_to_date('1488793728', '%Y-%m-%d')
    2017-03-06
    """
    return datetime.datetime.fromtimestamp(int(timestamp_str)).strftime(date_format)

#===============================================================================
# inside_bounding_box()
#===============================================================================
def inside_bounding_box(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, start_lat, start_lon, end_lat, end_lon):
    """
    Check if two given sets of coordinates (start_lat, start_lon) and (end_lat, end_lon) are
    within a bounding box (bb_minlat, bb_minlon, bb_maxlat, bb_maxlon)

    Examples:
    >>> inside_bounding_box(50.7777, 4.2359, 50.9204, 4.5216, 50.866232, 4.327700, 50.896571, 4.428547)
    True
    """
    return (bb_minlat <= start_lat <= bb_maxlat and bb_minlon <= start_lon <= bb_maxlon) and \
            (bb_minlat <= end_lat <= bb_maxlat and bb_minlon <= end_lon <= bb_maxlon)

#===============================================================================
# find_site_for_rides()
#===============================================================================
def find_site_for_rides(bb_minlat, bb_minlon, bb_maxlat, bb_maxlon, start_lat, start_lon, end_lat, end_lon):
    """
    Check if one or both sets of coordinates (start_lat, start_lon) and (end_lat, end_lon) are
    within a site's bounding box (bb_minlat, bb_minlon, bb_maxlat, bb_maxlon)
    """
    return (bb_minlat <= start_lat <= bb_maxlat and bb_minlon <= start_lon <= bb_maxlon) or \
            (bb_minlat <= end_lat <= bb_maxlat and bb_minlon <= end_lon <= bb_maxlon)   

#===============================================================================
# remove_non_ascii()
#===============================================================================
def remove_non_ascii(s):
    """
    Replace consecutive non-ASCII characters with a space:

    Examples:
    >>> re.sub(rb'[^\x00-\x7f]',rb' ',b)
    b'ABC      def'
    """
    return re.sub(r'[^\x00-\x7F]+',' ', s)

#===============================================================================
# waypoints_to_polyline ()
#===============================================================================
def waypoints_to_polyline(waypoints):
    """
    To use this function you need to install polyline library:
    https://pypi.python.org/pypi/polyline/

    Visualize the generated polyline on the map at:
    https://developers.google.com/maps/documentation/utilities/polylineutility

    """
    new_coordinate_set = []
    # for each coordinate set (long;lat)
    for coordinate_set in waypoints.split(','):
        temp_coordinate_set = coordinate_set.split(';')
        # check if both long and lat exist
        if len(temp_coordinate_set) > 1:
            new_coordinate_set.append(
                ( float(temp_coordinate_set[1]), float(temp_coordinate_set[0]) )
            )
    poly = polyline.encode(new_coordinate_set, 5)
    return poly

#===============================================================================
# generate_custom_objectid()
#===============================================================================
def generate_custom_objectid(s, l):
    """
    Generate a custom hex l-length ObjectId for MongoDB using md5 algorithm:

    Examples:
    >>> generate_custom_objectid('a013d9d4c046102a7849a8b3a56eee06a37769d4', 24)
    "58da1fe0b336eafd3590eea7"
    """
    string_to_bytes = bytearray(s, "ASCII")
    hashed_object = hashlib.md5(string_to_bytes)
    hexdig = hashed_object.hexdigest()[:l]
    return hexdig

#===============================================================================
# haversine_formula ()
#===============================================================================
def haversine_formula(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points 
    on the earth (specified in decimal degrees)
    """
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6367 * c
    return round(km, 1)
