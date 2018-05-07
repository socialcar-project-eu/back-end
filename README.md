# <a name="requirements"></a> Requirements

- Python3 & virtualenv
- MongoDB

To install them on Ubuntu/Debian:
```
sudo apt-get install mongodb python3 virtualenv
```



# <a name="installation"></a> Installation


```bash
git clone <repo-url>
cd socialcar-back-end/

# Create virtual environment
virtualenv --python=python3 env

# Activate virtual environment (use 'deactivate' to, well, deactivate it)
source env/bin/activate

# Install SocialCar server
pip3 install -e .

# Optionally, to use server with uWSGI or gunicorn
pip3 install uwsgi gunicorn
```



# <a name="sample_data"></a> Import sample site data

You can add the sites you want to support by inserting a corresponding entry in collection `sites` of MongoDB, in the form specified by the database schema (see `sites` in socialcar/settings.py). An example could be:
```bash
$ mongo socialcardb
MongoDB shell version: 2.6.10
connecting to: socialcardb
> db.sites.insert(
    {
      "name" : "Brussels",
      "url" : "<URL of the Route Planning service for this site>",
      "bounding_box" : {
          "max_lon" : 4.7736,
          "min_lon" : 3.9908,
          "max_lat" : 51.05,
          "min_lat" : 50.6373
      },
      "price_info" : {
          "currency" : "EUR"
      }
    }
  )
WriteResult({ "nInserted" : 1 })
```



# Run server

You can run the server in various modes using the `run-server.py` script:

```
usage: run-server.py [-h] [-w WORKERS] [--ssl] [--sentry] [--debug]
                     HOST PORT SERVER_MODE DBNAME FCM_HOST FCM_PORT

positional arguments:
  HOST                  Server HOST
  PORT                  Server PORT
  SERVER_MODE           builtin, uwsgi, gunicorn
  DBNAME                Database name
  FCM_HOST              FCM server ip or hostname
  FCM_PORT              FCM server port

optional arguments:
  -h, --help            show this help message and exit
  -w WORKERS, --workers WORKERS
                        Number of workers (default: 4)
  --ssl                 Use SSL (default: False)
  --sentry              Use sentry.io for notifications on errors and
                        exceptions (default: False)
  --debug               Run server in debug mode (default: False)
```

You can change the `HOST`, `PORT` and `WORKERS` according to your needs.

Built-in Eve server:
```
         127.0.0.1:5000
Client <----------------> Eve
```

Using uWSGI:
```
         127.0.0.1:5000
Client <----------------> uWSGI <---> Eve
```

Using gunicorn:
```
         127.0.0.1:5000
Client <----------------> gunicorn <---> Eve
```



## <a name="builtin"></a> Run built-in server

```bash
$ python3 run-server.py 127.0.0.1 5000 builtin socialcardb 127.0.0.1 8081 --debug
```

This mode is useful for **development** since it has debugging enabled (e.g. in
case of error the client gets a full stack trace).
Setting the number of workers has no effect since built-in server is
single-threaded.

**Warning: Single-threaded, debugging enabled. Do NOT use this mode in production!**

In case you get an error, see [error handling](#error_handling) section for some frequent errors and their solutions.


## <a name="uwsgi"></a> Run server using uWSGI

```bash
$ python3 run-server.py 127.0.0.1 5000 uwsgi socialcardb 127.0.0.1 8081 --sentry
```

`--sentry`: developers will get notified whenever an exception happens, using
[sentry.io](http://sentry.io).


## <a name="gunicorn"></a> Run server using gunicorn

```bash
$ python3 run-server.py 127.0.0.1 5000 gunicorn socialcardb 127.0.0.1 8081 --sentry
```

`--sentry`: developers will get notified whenever an exception happens, using
[sentry.io](http://sentry.io).



# Test server

Open http://127.0.0.1:5000/rest/v2/docs




# <a name="services"></a> Services

The server is based on a number of services that should run in order to operate correctly. The three core services are:
- [Route Planning service](https://github.com/socialcar-project-eu/route-planning)
- [Destination Tagging service](https://github.com/socialcar-project-eu/destination-tagging)
- [Feedback Evaluation service](https://github.com/socialcar-project-eu/feedback-evaluation)

It also relies on [Push Messaging server](http://socialcargit.cloudapp.net/socialcar/push-messaging-server) (or FCM server) for delivery of notifications.

Last, it relies on some internal services:

- **Lift completion service**: checks periodically the lifts stored in database, and marks as "completed" all lifts that have expired.

```
usage: Lift_Completion_Controller.py [-h] [-i INTERVAL] DBNAME

positional arguments:
  DBNAME                Database name

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        Interval to run this script periodically (secs)
                        (default: 60)
```
E.g. to start it: `python3 scripts/Lift_Completion_Controller.py socialcardb`

- **GTFS import service**: checks GTFS files for availability, structure and accessibility, exports Stops and Departure Times data and then imports the parsed data into the database’s corresponding collections.

```
usage: GTFS-import.py [-h] [-f FILE] [-d DIR] DBNAME

positional arguments:
  DBNAME                Database name

optional arguments:
  -h, --help  show this help message and exit
  -f FILE     zip file containg GTFS files (default: None)
  -d DIR      directory containg GTFS files (default: None)
```
E.g. to start it: `python3 scripts/GTFS-import.py socialcardb GTFS.zip`

- **Reports pull service**: checks periodically if there are new reports published on live data APIs, and if yes pulls them and imports them into database.

```
usage: Reports_Periodic_Pull.py [-h] [-i INTERVAL] [-n NEWERTHAN] [--ssl] HOST PORT DBNAME

positional arguments:
  HOST                  Server HOST (e.g. 'localhost')
  PORT                  Server PORT (e.g. '5000')
  DBNAME                Database name

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        Interval to run this script periodically (secs)
                        (default: 3600)
  -n NEWERTHAN, --newerThan NEWERTHAN
                        Timeframe to delete user reports older than (secs)
                        (default: 7200)
  --ssl                 Use SSL (default: False)
```
E.g. to start it: `python3 Reports_Periodic_Pull.py localhost 5000 socialcardb -i 3600 -n 7200 --ssl`

- **RDEX rides pull service**: checks periodically if there are new rides published on RDEX, and if yes pulls them and imports them into database.

```
usage: RDEX-periodic-pull.py [-h] [-i INTERVAL] [-r PERIOD] [-d RADIUS] [--ssl]
                             HOST PORT DBNAME CITY

positional arguments:
  HOST                  Server HOST (e.g. 'localhost')
  PORT                  Server PORT (e.g. '5000')
  DBNAME                Database name
  CITY                  City name - currently: brussels, edinburgh, ljubljana, ticino

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        Interval to run this script periodically (secs)
                        (default: 60)
  -r PERIOD, --period PERIOD
                        Retrieve all rides within a certain period (max 72 hours) 
                        (default: 12)
  -d RADIUS, --radius RADIUS
                        Retrieve all rides within a certain radius 
                        (default: 20)
  --ssl                 Use SSL (default: False)
```
E.g. to start it: `python3 RDEX-periodic-pull.py localhost 5000 socialcardb brussels -i 3600 -r 48 -d 40 --ssl`

- **Passenger ETA notification service**: after a trips starts, periodically informs the passenger on the estimated time of arrival of the driver.

```
usage: Passenger_ETA_Controller.py [-h] [-i INTERVAL] [-r RADIUS] [-p PERIOD]
                                   DBNAME

positional arguments:
  DBNAME                Database name

optional arguments:
  -h, --help            show this help message and exit
  -i INTERVAL, --interval INTERVAL
                        Interval to run this script periodically (secs)
                        (default: 600)
  -r RADIUS, --radius RADIUS
                        Send passenger notification within a certain radius
                        from lift start point (kms) (default: 5)
  -p PERIOD, --period PERIOD
                        Send passenger notification within a certain time
                        period from lift start date (secs) (default: 1800)
```
E.g. to start it: `python3 Passenger_ETA_Controller.py socialcardb -i 600 -r 5 -p 1800`



# <a name="admins"></a> Admins

You can add a users with administration priviledges (i.e., being able to
`GET`, `POST`, `PUT`, `PATCH`, `DELETE` all resources and items) by
inserting a corresponding entry in collection `admins` of MongoDB, e.g.:

```bash
$ mongo socialcardb
MongoDB shell version: 2.6.10
connecting to: socialcardb
> db.admins.insert({"username" : "admin", "password" : "adminpass"})
WriteResult({ "nInserted" : 1 })
```

This is useful for example in order to create admin accounts for the services
that must be able to modify some objects of the database that were not created
by them.



# <a name="environment_variables"></a> Environment variables

You may change the following environment variables. These are their default values:
```
MONGO_HOST="localhost"
MONGO_PORT=27017
MONGO_USERNAME=""
MONGO_PASSWORD=""
SENTRY_DSN="https://ccb...449@sentry.io/136957"
FCM_API_KEY='AAAAzxz0MLQ:APA91bEU..'
```



# <a name="error_handling"></a> Error handling

Errors below are from third-party libraries that have been patched for these
errors but patches are not yet included in their official release (i.e. PyPy).

**Error when starting server:**

```
Traceback (most recent call last):
  File "./socialcar/__init__.py", line 12, in <module>
    from eve_docs import eve_docs
  File "/PATH/TO/site-packages/eve_docs/__init__.py", line 2, in <module>
    from .config import get_cfg
  File "/PATH/TO/site-packages/eve_docs/config.py", line 11
    print base
             ^
SyntaxError: Missing parentheses in call to 'print'
```

**Solution:**

Edit `/PATH/TO/site-packages/eve_docs/config.py`, replace `print base` with `print(base)`.
In Linux just `sed -i 's/print base/print(base)/g' <filename>`.

**Error when updating a document:**

```
500 Internal Server Error

ERROR in mongo [/PATH/TO/site-packages/eve/io/mongo/mongo.py:482]:
After applying the update to the document {id: ObjectId('587755f34c23ec10c1f311a8') , ...}, the (immutable) field '_id' was found to have been altered to id: ObjectId('587755f34c23ec10c1f311aa')
```

**Solution:**

Edit `/PATH/TO/site-packages/eve/io/mongo/mongo.py`, find line that contains:
```
(server_version in ('2.6', '3.0') and e.code in (66, 16837))
```
change to:
```
(server_version in ('2.6', '3.0', '3.2', '3.4') and e.code in (66, 16837))
