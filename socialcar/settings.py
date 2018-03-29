# -*- coding: utf-8 -*-
import os
import pymongo

# Eve configuration global settings: http://python-eve.org/config.html

URL_PREFIX = 'rest'
API_VERSION = 'v2'
DEFAULT_HOST = 'localhost'
DEFAULT_PORT = '5000'

# DB connection and other settings are stored in environment variables
DEBUG = bool(os.environ.get('SOCIALCAR_DEBUG', False))
MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_DBNAME = os.environ.get('MONGO_DBNAME', 'socialcar' + API_VERSION.replace('.', '-'))
USE_SENTRY = bool(os.environ.get('USE_SENTRY', False))
SENTRY_DSN = os.environ.get('SENTRY_DSN', '{YOUR_SENTRY_DSN}') # TODO: Insert Sentry DSN key here
FCM_HOST = os.environ.get('FCM_HOST', 'localhost')
FCM_PORT = int(os.environ.get('FCM_PORT', 8081))
FCM_API_KEY = os.environ.get('FCM_API_KEY', '{YOUR_FCM_API_KEY}') # TODO: Insert FCM API key here

# Disable XML support (use only JSON)
XML = False

# Show database schema at this endpoint
SCHEMA_ENDPOINT = 'schema'

# Methods enabled for resources/collections (e.g. url.com/resource)
RESOURCE_METHODS = ['GET', 'POST']

# Methods enabled for individual items (e.g. url.com/resource/item)
ITEM_METHODS = ['GET', 'PUT', 'PATCH', 'DELETE']

# Hypermedia as the Engine of Application State
# http://python-eve.org/features.html#hateoas
HATEOAS = False

# When serving requests, matching JSON strings will be parsed and stored as
# datetime values. In responses, datetime values will be rendered as JSON
# strings using this format.
DATE_FORMAT = '%d/%m/%Y %H:%M:%S'

# Disable concurrency control
IF_MATCH = False

# Versioning: when we edit an object we also keep its previous version.
# http://python-eve.org/features.html#document-versioning
# TODO: Probably disable in production
VERSIONING = True

# Soft deletes: When deleting an object keep it in database but remove it from
# results on API requests
# http://python-eve.org/features.html#soft-delete
SOFT_DELETE = True

# Log all edit operations (POST, PATCH PUT and DELETE)
OPLOG = False

# When True, POST, PUT, and PATCH responses only return automatically handled
# meta fields such as object id, date_created. etc. When False, the entire
# document will be sent.
BANDWIDTH_SAVER = False

# Enable pagination for GET requests.
PAGINATION = False
# Each GET request returns at most these many objects
PAGINATION_DEFAULT = 50
# User can change the number of objects return on GET request using query
# parameter 'max_results' (e.g., &max_results=30). Values exceeding this
# pagination limit will be silently replaced with this value.
PAGINATION_LIMIT = 100
# Key for the pages query parameter
QUERY_PAGE = 'page'
# Key for the max results query parameter.
QUERY_MAX_RESULTS = 'limit'

# Enable Embedded Resource Serialization: if a document field is referencing
# a document in another resource, clients can request the referenced document
# to be embedded within the requested document.
# http://python-eve.org/features.html#embedded-docs
EMBEDDING = True
# Keyword to use for embedding a field. E.g. url.com/users?embed={'cars':1}
QUERY_EMBEDDED = 'embed'

# List of fields on which filtering is allowed. Can be set to [] (no filters
# allowed) or ['*'] (filters allowed on every field).
ALLOWED_FILTERS = [ ]

# Serving media files at a dedicated endpoint
# http://python-eve.org/features.html#serving-media-files-at-a-dedicated-endpoint
# Disable default behaviour, return media as URL instead
RETURN_MEDIA_AS_BASE64_STRING = False
RETURN_MEDIA_AS_URL = True
MEDIA_ENDPOINT = 'media'

#===============================================================================
# users
#===============================================================================
users = {
    'schema': {
        'email': {
            'type': 'string',
            'regex': r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$',
            'required': True,
            'unique': True,
        },
        'password': {
            'type': 'string',
            'minlength': 6,  # Document on app
            'required': True,
        },
        'name': {
            'type': 'string',
            'regex': r'^(?!\s*$).+',
            'required': True,
        },
        'phone': {
            'type': 'string',
            'required': True,
        },
        'dob': {  # date of birth
            'type': 'string',
            'regex': r'^\d{4}[\/\-]\d{2}[\/\-]\d{2}$',  # Validate dddd-dd-dd
            'required': False,
        },
        'gender': {
            'type': 'string',
            'allowed': [ 'MALE', 'FEMALE', 'OTHER' ],
            'required': False,
        },
        'fcm_token': {
            'type': 'string',
            'required': True,
        },
        'rating': {
            'type': 'integer',
            'min': 0,
            'max': 5,
            'default': 0,
            'required': False,  # Added by server
            'readonly': True,  # Only Reputation Assessment module can modify it
        },
        'cars': {
            'type': 'list',
            'schema': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'cars',
                    'field': '_id',
                },
            },
            'default': [],
            'required': False,  # Added by server
            'readonly': True,  # Automatically updated by server
        },
        'pictures': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    '_id': {
                        'type': 'objectid',
                        'data_relation': {
                            'resource': 'user_pictures',
                            'field': '_id',
                        },
                        'required': True,
                    },
                    'file': {
                        'type': 'string',
                        'required': True,
                    },
                },
            },
            'default': [],
            'required': False,  # Added by server
            'readonly': True,  # Automatically updated by server
        },
        'travel_preferences': {
            'type': 'dict',
            'schema': {
                'preferred_transport': {
                    'type': 'list',
                    'schema': {
                        'type': 'string',
                        'allowed': [ 'FEET', 'CAR_POOLING', 'METRO', 'BUS', 'RAIL', 'TRAM', 'FERRY', 'CABLECAR', 'GONDOLA', 'FUNICULAR' ],
                    },
                },
                'gps_tracking': {
                    'type': 'boolean'
                },
                'carpooler_preferred_gender': {
                    'type': 'string'
                },
                'carpooler_preferred_age_group': {
                    'type': 'string'
                },
                'special_request': {
                    'type': 'list',
                    'schema': {
                        'type': 'string',
                        'allowed': [ 'BLIND', 'WHEELCHAIR', 'DEAF', 'ELDERLY' ],
                    },
                },
                'max_transfers': {
                    'type': 'integer'
                },
                'max_cost': {
                    'type': 'integer'
                },
                'max_walk_distance': {
                    'type': 'integer'
                },
                'luggage': {
                    'type': 'boolean'
                },
                'optimisation': {
                    'type': 'list',
                    'schema': {
                        'type': 'string',
                        'allowed': [ 'FASTEST', 'SHORTEST', 'CHEAPEST', 'COMFORT', 'SAFEST' ],
                    },
                },
                'comfort_level': {
                    'type': 'integer'
                },
                'food': {
                    'type': 'boolean'
                },
                'pets': {
                    'type': 'boolean'
                },
                'smoking': {
                    'type': 'boolean'
                },
                'music': {
                    'type': 'boolean'
                },
            },
            'required': False,
        },
        'social_provider': {
            'type': 'dict',
            'schema': {
                'social_id': {
                    'type': 'string',
                },
                'social_network': {
                    'type': 'string',
                    'allowed': [ 'FACEBOOK', 'GOOGLE_PLUS' ],
                },
            },
            'required': False,
        },
        'platform': {
            'type': 'string',
            'allowed': [ 'ANDROID', 'IOS' ],
            'required': False,
        },
    },
    'public_methods': ['POST'],

    # Disable endpoint caching: we don't want client apps to cache account data.
    'cache_control': '',
    'cache_expires': 0,
}

#===============================================================================
# cars
#===============================================================================
cars = {
    'schema': {
        'plate': {
            'type': 'string',
            'required': True,
            'unique': True
        },
        'owner_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'model': {
            'type': 'string',
            'required': True,
        },
        'colour': {
            'type': 'string',
            'required': True,
        },
        'seats': {
            'type': 'integer',
            'required': True,
        },
        'pictures': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    '_id': {
                        'type': 'objectid',
                        'data_relation': {
                            'resource': 'car_pictures',
                            'field': '_id',
                        },
                        'required': True,
                    },
                    'file': {
                        'type': 'string',
                        'required': True,
                    },
                },
            },
            'default': [],
            'required': False,  # Added by server
            'readonly': True,  # Automatically updated by server
        },
        'car_usage_preferences': {
            'type': 'dict',
            'schema': {
                'air_conditioning': {
                    'type': 'boolean',
                    'required': True,
                },
                'child_seat': {
                    'type': 'boolean',
                    'required': True,
                },
                'food_allowed': {
                    'type': 'boolean',
                    'required': True,
                },
                'luggage_type': {
                    'type': 'string',
                    'allowed': [ 'NO', 'SMALL', 'MEDIUM', 'LARGE' ],
                    'required': True,
                },
                'pets_allowed': {
                    'type': 'boolean',
                    'required': True,
                },
                'smoking_allowed': {
                    'type': 'boolean',
                    'required': True,
                },
                'music_allowed': {
                    'type': 'boolean',
                    'required': True,
                },
            },
        },
    },
}

#===============================================================================
# rides
#===============================================================================
date_type = 'integer'

lat_lon_schema = {
    'lat': {
        'type': 'float',
        'required': True,
    },
    'lon': {
        'type': 'float',
        'required': True,
    },
}

rides = {
    'schema': {
        'driver_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'car_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'cars',
                'field': '_id',
            },
            'required': True,
        },
        'name': {
            'type': 'string',
            'required': True,
        },
        'start_point': {
            'type': 'dict',
            'schema': lat_lon_schema,
            'required': True,
        },
        'end_point': {
            'type': 'dict',
            'schema': lat_lon_schema,
            'required': True,
        },
        'date': {
            'type': date_type,
            'required': True,
        },
        'activated': {
            'type': 'boolean',
            'required': True,
        },
        'polyline': {
            'type': 'string',
            'required': True,
        },
        'seats_available': {
            'type': 'integer',
            'required': False,
        },
        'lifts': {
            'type': 'list',
            'schema': {
                'type': 'objectid',
                'data_relation': {
                    'resource': 'lifts',
                    'field': '_id',
                    'embeddable': True,
                },
            },
            'default': [],
            'required': False,  # Added by server
            'readonly': True,  # Automatically updated by server
        },
        'extras': {
            'type': 'dict',
            'required': False,
        },
    },
}

#===============================================================================
# rides_boundary
#===============================================================================
rides_boundary = {
    'url': 'rides_boundary',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# rides_internal
#===============================================================================
rides_internal = {
    'url': 'rides_internal',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# trips
#===============================================================================
point_date_address_schema = {
    'point': {
        'type': 'dict',
        'schema': lat_lon_schema,
        'required': True,
    },
    'date': {
        'type': date_type,
        'required': True,
    },
    'address': {
        'type': 'string',
        'required': True,
    },
}

transport_pt = {
    'travel_mode': {
        'type': 'string',
        'allowed': [ 'METRO', 'BUS', 'RAIL', 'TRAM' ],
        'required': True,
    },
    'short_name': {
        'type': 'string',
        'required': True,
    },
    'long_name': {
        'type': 'string',
        'required': True,
    },
}

transport_feet = {
    'travel_mode': {
        'type': 'string',
        'allowed': [ 'FEET' ],
        'required': True,
    },
    'short_name': {
        'type': 'string',
        'required': True,
    },
    'long_name': {
        'type': 'string',
        'required': True,
    },
}

transport_carpooling = {
    'travel_mode': {
        'type': 'string',
        'allowed': [ 'CAR_POOLING' ],
        'required': True,
    },
    'ride_id': {
        'type': 'string',
        # 'type': 'objectid',  # Validation error: error converting string to ObjectId
        'data_relation': {
            'resource': 'rides',
            'field': '_id',
        },
        'required': True,
    },
    'driver_id': {
        'type': 'string',
        # 'type': 'objectid',  # Validation error: error converting string to ObjectId
        'data_relation': {
            'resource': 'users',
            'field': '_id',
        },
        'required': True,
    },
    'car_id': {
        'type': 'string',
        # 'type': 'objectid',  # Validation error: error converting string to ObjectId
        'data_relation': {
            'resource': 'cars',
            'field': '_id',
        },
        'required': True,
    },
    'public_uri': {
        'type': 'string',
        'required': False,
    },
}

trip = {
    'steps': {
        'type': 'list',
        'schema': {
            'type': 'dict',
            'schema': {
                'route': {
                    'type': 'dict',
                    'schema': {
                        'start_point': {
                            'type': 'dict',
                            'schema': point_date_address_schema,
                            'required': True,
                        },
                        'end_point': {
                            'type': 'dict',
                            'schema': point_date_address_schema,
                            'required': True,
                        },
                        'intermediate_points': {
                            'type': 'list',
                            'schema': {
                                'type': 'dict',
                                'schema': point_date_address_schema,
                            },
                            'required': False,
                        }
                    },
                    'required': True,
                },
                'transport': {
                    'type': 'dict',
                    'anyof': [
                        { 'schema': transport_pt },
                        { 'schema': transport_feet },
                        { 'schema': transport_carpooling },
                    ],
                    'required': True,
                },
                'price': {
                    'type': 'dict',
                    'schema': {
                        'amount': {
                            'type': 'float',
                            'required': True,
                        },
                        'currency': {
                            'type': 'string',
                            'required': True,
                        },
                    },
                    'required': True,
                },
                'distance': {
                    'type': 'integer',
                    'required': True,
                },
            },
            'required': True,
        },
        'required': True,
    },
}

trips = {
    'schema': trip,

    # Read-only endpoint. Returned trips will be embedded on lifts
    'resource_methods': [ 'GET' ],
    'item_methods': [ ],
}

#===============================================================================
# lifts
#===============================================================================
lifts = {
    'schema': {
        'ride_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'rides',
                'field': '_id',
            },
            'required': True,
        },
        'trip': {
            'type': 'dict',
            'schema': trip,
            'required': True,
        },
        'driver_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'passenger_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'car_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'cars',
                'field': '_id',
            },
            'required': True,
        },
        'status': {
            'type': 'string',
            'allowed': [ 'PENDING', 'ACTIVE', 'REFUSED', 'CANCELLED', 'COMPLETED' ],
            'required': True,
        },
        'start_point': {
            'type': 'dict',
            'schema': point_date_address_schema,
            'required': True,
        },
        'end_point': {
            'type': 'dict',
            'schema': point_date_address_schema,
            'required': True,
        },
    },
}

#===============================================================================
# feedbacks
#===============================================================================
feedbacks_schema = {
    'role': {
        'type': 'string',
        'allowed': ['driver', 'passenger'],
        'required': True,
    },
    'lift_id': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'lifts',
            'field': '_id',
        },
        'required': True,
    },
    'reviewed_id': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'users',
            'field': '_id',
        },
        'required': True,
    },
    'reviewer_id': {
        'type': 'objectid',
        'data_relation': {
            'resource': 'users',
            'field': '_id',
        },
        'required': True,
    },
    'review': {
        'type': 'string',
        'required': True,
    },
    'rating': {  # TODO: Will be replaced by field in 'ratings'
        'type': 'integer',
        'required': True,
    },
    'ratings': {
        'type': 'dict',
        'valueschema': {
             'type': 'integer',
             'min': 1,
             'max': 5,
         },
        # 'required': True,  # TODO: Temporarily not required, until Movenda updates the app
    },
    'date': {
        'type': date_type,
        'required': True,
    },
}

feedbacks = {
    'url': 'feedbacks/users/<regex("[a-f0-9]{24}"):reviewed_id>/<regex("[a-z].*"):role>',
    'datasource': {
        'source': 'feedbacks',
    },
    'schema': feedbacks_schema,
}

feedbacks_all = {
    'url': 'feedbacks',
    'datasource': {
        'source': 'feedbacks',
    },
    'schema': feedbacks_schema
}

#===============================================================================
# feedbacks_summary
#===============================================================================
feedbacks_summary = {
    'schema': {
        'user_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
            'unique': True,
        },
        'last_update': {
            'type': date_type,
            'required': True,
        },
        'ratings': {
            'type': 'dict',
            'valueschema': {
                 'type': 'list',
                 'schema': {
                    'type': 'integer',
                 },
                 'minlength': 5,
                 'maxlength': 5,
             },
            'required': True,
        },
    },
    'public_methods': ['GET'],  # Automatically updated by server
}

#===============================================================================
# reputations
#===============================================================================
reputations = {
    'schema': {
        'user_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
            'unique': True,
        },
        'reputation': {
            'type': 'integer',
            'min': 0,
            'max': 5,
            'default': 3,
            'required': False,  # Added by server
        },
        'r': {
            'type': 'integer',
            'default': 0,
            'required': False,  # Added by server
        },
        's': {
            'type': 'integer',
            'default': 0,
            'required': False,  # Added by server
        },
        'last_update': {
            'type': date_type,
            'required': True,
        },
    },
}

#===============================================================================
# user_pictures
#===============================================================================
user_pictures = {
    'schema': {
        'user_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'file': {
            'type': 'media',
            'required': True,
        },
    }
}

user_pictures_alt = {
    'url': 'pictures/users/<regex("[a-f0-9]{24}"):user_id>',
    'datasource': {
        'source': 'user_pictures',
    },
    'schema': {
        'file': {
            'type': 'media',
            'required': True,
        },
    }
}

#===============================================================================
# car_pictures
#===============================================================================
car_pictures = {
    'schema': {
        'car_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'cars',
                'field': '_id',
            },
            'required': True,
        },
        'file': {
            'type': 'media',
            'required': True,
        },
    }
}

#===============================================================================
# positions
#===============================================================================
positions = {
    'schema': {
        'user_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'point': {
            'type': 'dict',
            'schema': lat_lon_schema,
            'required': True,
        },
        'timestamp': {
            'type': date_type,
            'required': True,
        },
    }
}

#===============================================================================
# destinations
#===============================================================================
destinations = {
    'schema': {
        'user_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
            'unique': True,
        },
        'destinations': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'type': {
                        'type': 'string',
                        'required': True,
                    },
                    'point': {
                        'type': 'dict',
                        'schema': lat_lon_schema,
                        'required': True,
                    },
                    'last_update': {
                        'type': date_type,
                        'required': True,
                    },
                }
            }
        },
    }
}

#===============================================================================
# sites
#===============================================================================
sites = {
    'schema': {
        'name': {
            'type': 'string',
            'required': True,
        },
        'url': {
            'type': 'string',
            'required': True,
        },
        'bounding_box': {
            'type': 'dict',
            'schema': {
                'min_lat': {
                    'type': 'float',
                    'required': True,
                },
                'min_lon': {
                    'type': 'float',
                    'required': True,
                },
                'max_lat': {
                    'type': 'float',
                    'required': True,
                },
                'max_lon': {
                    'type': 'float',
                    'required': True,
                },
            },
            'required': True,
        },
        'carpooling_info': {
            'type': 'dict',
            'schema': {
                'version': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'nightly_version': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'updated': {
                    'type': date_type,
                    'required': True,
                },
                'nightly_updated': {
                    'type': date_type,
                    'required': True,
                },
            }
        },
        'reports_info': {
            'type': 'dict',
            'schema': {
                'version': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'updated': {
                    'type': date_type,
                    'required': True,
                },
            }
        },
        'price_info': {
            'type': 'dict',
            'schema': {
                'currency': {
                    'type': 'string',
                    'required': True,
                },
            }
        },
        'external_carpooling': {
            'type': 'list',
            'schema': {
                'type': 'dict',
                'schema': {
                    'username': {
                        'type': 'string',
                        'required': False,
                    },
                    'uuid': {
                        'type': 'string',
                        'required': False,
                    },
                    'url': {
                        'type': 'string',
                        'required': False,
                    },
                },
            },
            'default': [],
            'required': False,
            'readonly': True,
        },
        'users': {
            'type': 'list',
            'schema': {
                'type': 'string',
                'required': False
            },
            'default': [],
            'required': False,
            'readonly': True
        },
       'ride_details': {
            'type': 'dict',
            'schema': {
                'internal': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'external': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'carpooling_only': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'carpooling_PT': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
                'total_solutions': {
                    'type': 'integer',
                    'default': 0,
                    'required': True,
                },
            }
        },
    },
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
}

#===============================================================================
# sites_boundary
#===============================================================================
sites_boundary = {
    'url': 'sites_boundary',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# reports
#===============================================================================
reports = {
    'schema': {
        'location': {
            'type': 'dict',
            'schema': {
                'address': {
                    'type': 'string',
                },
                'geometry': {
                    'type': 'point',
                },
            },
            'required': True,
        },
        'category': {
            'type': 'string',
            'allowed': [ 'TRAFFIC', 'WORKS', 'ACCIDENT' ],
            'required': True,
        },
        'severity': {
            'type': 'string',
            'allowed': [ 'LOW', 'MEDIUM', 'HIGH' ],
            'required': True,
        },
        'timestamp': {
            'type': date_type,
            'required': False,  # Added by server
        },
        'source': {
            'type': 'string',
            'allowed': [ 'USER', 'API' ],
            'required': True,
        },
    },
    'mongo_indexes': {
        '2dsphere': [ ('location.geometry', pymongo.GEOSPHERE) ]
    },
}

#===============================================================================
# reports_boundary
#===============================================================================
reports_boundary = {
    'url': 'reports_boundary',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# reports-around
#===============================================================================
reports_around = {
    'url': 'reports-around',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ ],
    # Without this datasource field, each GET request on resource endpoint
    # will first get *all* docs from 'stops' collection, before replacing them
    # with the custom stops
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# stops
#===============================================================================
stops = {
    'url': 'public-transport/stops-around',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ ],
    # Without this datasource field, each GET request on resource endpoint
    # will first get *all* docs from 'stops' collection, before replacing them
    # with the custom stops
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# waiting_times
#===============================================================================
waiting_time = {
    'url': 'public-transport/waiting-time/<regex(".*"):stop_code>',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    # Without this datasource field, each GET request on resource endpoint
    # will first get *all* docs from 'stops' collection, before replacing them
    # with the custom stops
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

#===============================================================================
# messages
#===============================================================================
messages = {
    'schema': {
        'sender_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'sender_name': {
            'type': 'string',
            'required': False,  # Added by server
        },
        'receiver_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'users',
                'field': '_id',
            },
            'required': True,
        },
        'receiver_name': {
            'type': 'string',
            'required': False,  # Added by server
        },
        'lift_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'lifts',
                'field': '_id',
            },
            'required': True,
        },
        'timestamp': {
            'type': date_type,
            'required': False,
        },
        'body': {
            'type': 'string',
            'required': True,
        },
    },
}

#===============================================================================
# eta_notify
#===============================================================================
eta_notify = {
    # Read-only endpoint
    'schema': {
        'lift_id': {
            'type': 'objectid',
            'data_relation': {
                'resource': 'lifts',
                'field': '_id',
            },
            'required': True,
            'unique': True,
        }
    }
}

#===============================================================================
# positions_button
#===============================================================================
positions_button = {
    'url': 'positions_button',
    # Read-only endpoint
    'resource_methods': [ 'GET' ],
    'item_methods': [ 'GET' ],
    'datasource': {
        'source': 'nonExistingCollection',
    },
}

# The DOMAIN dict explains which resources will be available and how they will
# be accessible to the API consumer.
DOMAIN = {
    'users': users,
    'cars': cars,
    'trips': trips,
    'rides': rides,
    'rides_boundary': rides_boundary,
    'rides_internal': rides_internal,
    'lifts': lifts,
    'feedbacks': feedbacks,
    'feedbacks_all': feedbacks_all,
    'feedbacks_summary': feedbacks_summary,
    'reputations': reputations,
    'user_pictures': user_pictures,
    'user_pictures_alt': user_pictures_alt,
    'car_pictures': car_pictures,
    'positions': positions,
    'destinations': destinations,
    'sites': sites,
    'sites_boundary': sites_boundary,
    'reports': reports,
    'reports_boundary': reports_boundary,
    'reports_around': reports_around,
    'stops': stops,
    'waiting_time': waiting_time,
    'messages': messages,
    'eta_notify': eta_notify,
    'positions_button': positions_button,
}
