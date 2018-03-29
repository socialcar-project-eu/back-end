import os
import pymongo
import sys
import argparse
import requests
import json
import time, datetime, threading
from requests.auth import HTTPBasicAuth
from requests.packages.urllib3.exceptions import InsecureRequestWarning
from socialcar.utils import generate_custom_objectid, str_to_oid, oid_to_str

MONGO_HOST = os.environ.get('MONGO_HOST', 'localhost')
MONGO_PORT = int(os.environ.get('MONGO_PORT', 27017))
MONGO_USERNAME = os.environ.get('MONGO_USERNAME', '')
MONGO_PASSWORD = os.environ.get('MONGO_PASSWORD', '')
MONGO_REPORTS_COLLECTION = 'reports'

INCIDENTS_TYPE_TO_REPORT = {
    0: 'WORKS',       # Unknown
    1: 'ACCIDENT',    # Accident
    2: 'TRAFFIC',     # Fog
    3: 'TRAFFIC',     # Dangerous Conditions
    4: 'TRAFFIC',     # Rain
    5: 'TRAFFIC',     # Ice
    6: 'TRAFFIC',     # Jam
    7: 'WORKS',       # Lane Closed
    8: 'WORKS',       # Road Closed
    9: 'WORKS',       # Road Works
    10: 'TRAFFIC',    # Wind
    11: 'TRAFFIC',    # Flooding
    12: 'TRAFFIC',    # Detour
    13: 'TRAFFIC',    # Cluster 
}

INCIDENTS_SEVERITY_TO_REPORT = {
    0: 'MEDIUM',      # Unknown
    1: 'LOW',         # minor 
    2: 'MEDIUM',      # moderate 
    3: 'HIGH',        # major 
    4: 'HIGH',        # undefined, used for road closures and other indefinite delays
}

#===============================================================================
# periodic_pull ()
#===============================================================================
def periodic_pull(host, port, interval, dbname, newerThan, use_ssl):
    print('%s - Checking for reports data...' % (datetime.datetime.utcnow().strftime('%d-%m-%Y @ %H:%M:%S (UTC)')))

    client = pymongo.MongoClient(MONGO_HOST, MONGO_PORT)
    db = client[dbname]
    reports_collection = db[MONGO_REPORTS_COLLECTION]

    timeframe = int(time.time()) - int(newerThan)
    ids_to_keep = []
    counter_api = 0
    counter_user = 0
    prefix = "https" if use_ssl else "http"

    # Disable SSL warnings
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    # URLs
    sites_url = "%s://%s:%s/rest/v2/sites" % (prefix, host, port)
    reports_url = "%s://%s:%s/rest/v2/reports" % (prefix, host, port)
    # Parameters
    auth = HTTPBasicAuth('admin', 'password') # TODO: Insert admin credentials here
    headers = {'content-type': 'application/json'}

    #-----------------------------------------------------------------------
    # Fetch new reports
    #-----------------------------------------------------------------------
    # GET request for sites
    get_res_sites = requests.get(sites_url, headers=headers, auth=auth, verify=False)
    r_json = json.loads(get_res_sites.text)

    try:
        # For every site
        for site in r_json['sites']:
            min_lat = site['bounding_box']['min_lat']
            min_lon = site['bounding_box']['min_lon']
            max_lat = site['bounding_box']['max_lat']
            max_lon = site['bounding_box']['max_lon']
            reports = []

            # GET TomTom incidents URL
            url_incidents = "https://api.tomtom.com/traffic/services/4/incidentDetails/s3/%s,%s,%s,%s/11/1335294634919/json?key={API_KEY}" % (min_lat,min_lon,max_lat,max_lon) # TODO: Insert TomTom key here
            # GET request for TomTom incidents
            get_res_incidents = requests.get(url_incidents, headers=headers)
            r_json = json.loads(get_res_incidents.text)

            try:
                # For every fetched incident
                for incident in r_json['tm']['poi']:
                    # Generate and store custom uuid
                    uuid = generate_custom_objectid(incident['id'], 24)
                    ids_to_keep.append(uuid)
                    
                    # Fetch report with uuid from database
                    cursor_reports = reports_collection.find({ '_id': str_to_oid(uuid) })

                    # If report not in database
                    if cursor_reports.count() == 0:
                        incident_data = {
                            '_id': uuid,
                            'location': {
                                'address': incident['f'] if 'f' in incident else 'Unknown address',
                                'geometry': {
                                    'type': 'Point',
                                    'coordinates': [ incident['p']['x'], incident['p']['y'] ]
                                },
                            },
                            'category': INCIDENTS_TYPE_TO_REPORT[incident['ic']],
                            'severity': INCIDENTS_SEVERITY_TO_REPORT[incident['ty']],
                            'source': 'API'
                        }
                        reports.append(incident_data)

                # If there are reports to POST
                if len(reports) > 0:
                    json_body = json.dumps(reports)

                    # POST reports request
                    post_res_reports = requests.post(reports_url, data=json_body, headers=headers, auth=auth, verify=False)
                    if post_res_reports.status_code == 201:
                        print('    %s incident reports added to database for %s' % (len(reports), site['name']))
                    else:
                        print('    Error when posting incident reports into database for %s' % (site['name']))
                else:
                        print('    0 incident reports added to database for %s' % (site['name']))
            except KeyError:
                print('    No incident data for %s' % (site['name']))
    except KeyError:
        print("%s | %s - %s" % (get_res_sites.status_code, get_res_sites.url, get_res_sites.text))
        return

    #-----------------------------------------------------------------------
    # Delete obsolete reports
    #-----------------------------------------------------------------------
    # Fetch all reports from database
    cursor_reports = reports_collection.find({ '_deleted': {'$eq': False} })

    # For every report
    for report in cursor_reports:
        if report['source'] == 'API' and oid_to_str(report['_id']) not in ids_to_keep:
            # DELETE API reports if they are not included in TomTom
            delete_reports_url = '%s/%s' % (reports_url, report['_id'])
            delete_res_reports = requests.delete(delete_reports_url, headers=headers, auth=auth, verify=False)
            if delete_res_reports.status_code == 204:
                counter_api = counter_api + 1
        elif report['source'] == 'USER' and report['timestamp'] <= timeframe:
            # DELETE USER reports if they are older than newerThan parameter
            delete_reports_url = '%s/%s' % (reports_url, report['_id'])
            delete_res_reports = requests.delete(delete_reports_url, headers=headers, auth=auth, verify=False)
            if delete_res_reports.status_code == 204:
                counter_user = counter_user + 1
    print('    -------------------------------------------------------')
    print('    %s obsolete API reports deleted from database' % counter_api)
    print('    %s obsolete user reports deleted from database' % counter_user)

#===============================================================================
# run_periodically ()
#===============================================================================
def run_periodically(host, port, interval, dbname, newerThan, use_ssl):
    # This implementation is subject to change
    threading.Timer(interval, run_periodically, args=(host, port, interval, dbname, newerThan, use_ssl)).start()
    periodic_pull(host, port, interval, dbname, newerThan, use_ssl)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('h', metavar='HOST', help="Server HOST (e.g. 'localhost')", type=str)
    parser.add_argument('p', metavar='PORT', help="Server PORT (e.g. '5000')", type=str)
    parser.add_argument('dbname', metavar='DBNAME', help="Database name", type=str)
    parser.add_argument('-i', '--interval', metavar='INTERVAL', help="Interval to run this script periodically (secs)", type=int, default=3600)         # 1 hour
    parser.add_argument('-n', '--newerThan', metavar='NEWERTHAN', help="Timeframe to delete user reports older than (secs)", type=int, default=7200)    # 2 hours
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
    newerThan = args.newerThan
    host = args.h
    port = args.p
    use_ssl = args.ssl

    print('dbname:      %s' % (dbname))
    print('interval:      %s' % (interval))
    print('newerThan:      %s' % (newerThan))
    print(' * Reports Periodic Pull Service is active! * ')

    run_periodically(host, port, interval, dbname, newerThan, use_ssl)

if __name__ == '__main__':
    main()
