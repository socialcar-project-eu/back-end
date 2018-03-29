#!/usr/bin/env python3
import os
import sys
import argparse
import subprocess
import time
import tempfile
import signal
import importlib

MODES = [ 'builtin', 'uwsgi', 'gunicorn' ]
SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))
VIRTUALENV_FOLDER = os.path.join(SCRIPT_PATH, 'env')
VIRTUALENV_ACTIVATE = os.path.join(VIRTUALENV_FOLDER, 'bin', 'activate')
SSL_FOLDER = 'certificate'
SSL_CERT_FILE = os.path.join(SSL_FOLDER, 'socialcar.crt')
SSL_KEY_FILE = os.path.join(SSL_FOLDER, 'socialcar.key')
PYTHON = {
    'bin': os.path.join(VIRTUALENV_FOLDER, 'bin', 'python3')
}
EVE = {
    'module': 'eve',
    'install': 'pip3 install -e %s' % SCRIPT_PATH
}
UWSGI = {
    'bin': os.path.join(VIRTUALENV_FOLDER, 'bin', 'uwsgi'),
    'install': 'pip3 install uwsgi'
}
GUNICORN = {
    'bin': os.path.join(VIRTUALENV_FOLDER, 'bin', 'gunicorn'),
    'install': 'pip3 install gunicorn'
}

#===============================================================================
# run_server ()
#===============================================================================
def run_server(host, port, mode, dbname, fcm_host, fcm_port, workers, use_ssl, use_sentry, debug_mode):
    print('server:      %s:%s' % (host, port))
    print('mode:        %s' % (mode))
    print('dbname:      %s' % (dbname))
    print('fcm_server:  %s:%s' % (fcm_host, fcm_port))
    print('workers:     %s' % (workers))
    print('use_sentry:  %s' % (use_sentry))
    print('debug_mode:  %s' % (debug_mode))

    if use_sentry:
        os.environ['USE_SENTRY'] = 'True'
    if debug_mode:
        print(" *** Debug enabled! ***")
        os.environ['SOCIALCAR_DEBUG'] = 'True'
    os.environ['MONGO_DBNAME'] = dbname
    os.environ['FCM_HOST'] = fcm_host
    os.environ['FCM_PORT'] = fcm_port
    # TODO: maybe check here fcm server before starting?

    if mode == 'builtin':
        run_builtin_server(host, port, workers, use_ssl)
    elif mode == 'uwsgi':
        run_uwsgi_server(host, port, workers, use_ssl)
    elif mode == 'gunicorn':
        run_gunicorn_server(host, port, workers, use_ssl)
    else:
        print("Server mode '%s' not yet implemented" % mode)
        sys.exit(1)

#===============================================================================
# run_builtin_server ()
#===============================================================================
def run_builtin_server(host, port, workers, use_ssl):
    os.environ['SERVER_HOST'] = host
    os.environ['SERVER_PORT'] = port
    cmd = (
        PYTHON['bin'] +
        ' WSGI.py'
    )
    if use_ssl:
        cmd += ' --ssl %s,%s' % (SSL_CERT_FILE, SSL_KEY_FILE)

    print(" *** Do not use in production! (single thread) ***")
    execute_cmd(cmd)

#===============================================================================
# run_uwsgi_server ()
#===============================================================================
def run_uwsgi_server(host, port, workers, use_ssl):
    cmd = (
        UWSGI['bin'] +
        ' --processes %d' % (workers) +
        ' --enable-threads --thunder-lock --master'
        ' --module WSGI:app'
    )
    if use_ssl:
        cmd += ' --https %s:%s,%s,%s' % (host, port, SSL_CERT_FILE, SSL_KEY_FILE)
    else:
        cmd += ' --http %s:%s' % (host, port)

    ensure_module_or_binary_installed(UWSGI)
    execute_cmd(cmd)

#===============================================================================
# run_gunicorn_server ()
#===============================================================================
def run_gunicorn_server(host, port, workers, use_ssl):
    cmd = (
        GUNICORN['bin'] +
        ' --bind %s:%s' % (host, port) +
        ' --workers %d' % (workers) +
        ' --timeout 60' +
        ' WSGI:app'
    )
    if use_ssl:
        cmd += ' --certfile=%s --keyfile=%s' % (SSL_CERT_FILE, SSL_KEY_FILE)

    ensure_module_or_binary_installed(GUNICORN)
    execute_cmd(cmd)

#===============================================================================
# execute_cmd ()
#===============================================================================
def execute_cmd(cmd):
    print('Command: %s' % cmd)
    # Create a new process that will run cmd
    p = subprocess.Popen(cmd.split(), cwd=SCRIPT_PATH)
    try:
        # Wait child process while executing
        p.wait()
    except KeyboardInterrupt:
        # In case we got Control+C, child process will also get the singal and
        # start shutting down gracefully. Wait for shutdown.
        p.wait()

#===============================================================================
# ensure_virtualenv_installed_and_activated ()
#===============================================================================
def ensure_virtualenv_installed_and_activated():
    # If virtualenv directory does not exist
    if not os.path.isdir(VIRTUALENV_FOLDER):
        print("Directory '%s' not found. Create it with " % VIRTUALENV_FOLDER +
              "'virtualenv --python=python3 %s'" % VIRTUALENV_FOLDER)
        sys.exit(1)

    # If we are not running inside virtualenv
    if not hasattr(sys, 'real_prefix'):
        print("Virtualenv not activated. Activate with 'source %s'" %
              VIRTUALENV_ACTIVATE)
        sys.exit(1)

#===============================================================================
# ensure_module_or_binary_installed ()
#===============================================================================
def ensure_module_or_binary_installed(m):
    error = False

    # It's a module
    if 'module' in m:
        try:
            importlib.import_module(m['module'])
        except ImportError:
            error = True
    # It's a binary
    elif 'bin' in m:
        if not os.path.isfile(m['bin']):
            error = True

    if error:
        print("%s '%s' not found. Install it with '%s'" %
              ('Binary' if 'bin' in m else 'Module',
               m['bin'] if 'bin' in m else m['module'],
               m['install']))
        sys.exit(1)

#===============================================================================
# create_arg_parser ()
#===============================================================================
def create_arg_parser():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument('h', metavar='HOST', help="Server HOST", type=str)
    parser.add_argument('p', metavar='PORT', help="Server PORT", type=str)
    parser.add_argument('m', metavar='SERVER_MODE', help=", ".join(MODES), choices=MODES, type=str)
    parser.add_argument('d', metavar='DBNAME', help="Database name", type=str)
    parser.add_argument('fh', metavar='FCM_HOST', help="FCM server ip or hostname", type=str)
    parser.add_argument('fp', metavar='FCM_PORT', help="FCM server port", type=str)
    parser.add_argument('-w', '--workers', metavar='WORKERS', help="Number of workers", type=int, default=4)
    parser.add_argument('--ssl', help="Use SSL", action='store_true', default=False)
    parser.add_argument('--sentry', help="Use sentry.io for notifications on errors and exceptions", action='store_true', default=False)
    parser.add_argument('--debug', help="Run server in debug mode", action='store_true', default=False)
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
    host = args.h
    port = args.p
    mode = args.m
    dbname = args.d
    fcm_host = args.fh
    fcm_port = args.fp
    workers = args.workers
    use_ssl = args.ssl
    use_sentry = args.sentry
    debug_mode = args.debug

    ensure_virtualenv_installed_and_activated()
    ensure_module_or_binary_installed(EVE)
    run_server(host, port, mode, dbname, fcm_host, fcm_port, workers, use_ssl, use_sentry, debug_mode)

if __name__ == '__main__':
    main()
