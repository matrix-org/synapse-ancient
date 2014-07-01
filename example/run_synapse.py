#!/usr/bin/env python
# -*- coding: utf-8 -*-
from synapse.protocol.http import TwistedHttpServer, TwistedHttpClient
from synapse.transport import TransportLayer
from synapse.transaction import TransactionLayer
from synapse.pdu import PduLayer
from synapse.messaging import MessagingLayer, MessagingCallbacks
from synapse.api.server import SynapseHomeServer

from synapse.util import dbutils
from synapse.util import stringutils

from twistar.registry import Registry

from twisted.internet import reactor, defer
from twisted.enterprise import adbapi
from twisted.python.log import PythonLoggingObserver

import argparse
import logging
import re
import sqlite3

def setup_server(hostname):
    """ Sets up a home server.

    Args:
        hostname : The hostname for the server.
    Returns:
        A synapse home server
    """
    print "Server hostname: %s" % hostname
    http_server = TwistedHttpServer()
    http_client = TwistedHttpClient()

    transport_layer = TransportLayer(hostname, http_server, http_client)
    transaction_layer = TransactionLayer(hostname, transport_layer)
    pdu_layer = PduLayer(transport_layer, transaction_layer)

    messaging = MessagingLayer(hostname, transport_layer, pdu_layer)

    hs = SynapseHomeServer(http_server, hostname, messaging)
    return http_server

def setup_db(db_name):
    """ Set up all the dbs. Since all the *.sql have IF NOT EXISTS, so we don't
    have to worry about overwriting existing content.

    Args:
        db_name : The path to the database.
    """
    print "Preparing database: %s..." % db_name
    pool = adbapi.ConnectionPool(
        'sqlite3', db_name, check_same_thread=False,
        cp_min=1, cp_max=1)

    # set the dbpool global so other layers can access it
    dbutils.set_db_pool(pool)
    Registry.DBPOOL = pool

    schemas = [
            "schema/transactions.sql",
            "schema/pdu.sql",
            "schema/users.sql",
            "schema/im.sql"
    ]

    for sql_loc in schemas:
        with open(sql_loc, "r") as sql_file:
            sql_script = sql_file.read()

        with sqlite3.connect(db_name) as db_conn:
            c = db_conn.cursor()
            c.executescript(sql_script)
            c.close()
            db_conn.commit()

def setup_logging(verbosity, location):
    """ Sets up logging with set verbosity levels.

    Args:
        verbosity : The verbosity level.
        location : The location to write logs to.
    """
    print "Logs stored at %s" % location
    root_logger = logging.getLogger()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
            '%(message)s')
    fh = logging.FileHandler(location)
    fh.setFormatter(formatter)

    root_logger.addHandler(fh)
    root_logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    if verbosity > 1:
        root_logger.addHandler(sh)
    elif verbosity == 1:
        logger.addHandler(sh)

    observer = PythonLoggingObserver()
    observer.start()

def main(port, db, host, verbose):
    host = host if host else "localhost"

    setup_logging(verbose, "logs/%s"%host)  

    # setup and run with defaults if not specified
    setup_db(db if db else "proto_synapse.db")
    server = setup_server(host)
    server.start_listening(port if port else 8080)

    reactor.run()

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", dest="port", type=int, help="The port to listen on.")
    parser.add_argument("-d", "--database", dest="db", help="The database name.")
    parser.add_argument("-H", "--host", dest="host", help="The hostname of the server.")
    parser.add_argument('-v', '--verbose', dest="verbose", action='count', help="The verbosity level.")
    args = parser.parse_args()

    main(args.port, args.db, args.host, args.verbose)
    
