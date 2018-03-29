# -*- coding: utf-8 -*-
import os
import ssl
import sys
from socialcar import app
from socialcar.settings import DEFAULT_HOST, DEFAULT_PORT, DEBUG

SCRIPT_PATH = os.path.dirname(os.path.realpath(__file__))

#===============================================================================
# main ()
#===============================================================================
if __name__ == '__main__':

    server_host = os.environ.get('SERVER_HOST', DEFAULT_HOST)
    server_port = int(os.environ.get('SERVER_PORT', DEFAULT_PORT))

    # User may optionally pass argument '-ssl <cert file>,<key file>'
    ssl_context = None
    if len(sys.argv) == 3 and sys.argv[1] == '--ssl':
        cert, key = sys.argv[2].split(',')
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
        ssl_context.load_cert_chain(cert, key)

    app.run(host=server_host, port=server_port, debug=DEBUG, ssl_context=ssl_context)
