#!/usr/bin/env python
# -*- coding: utf-8 -*-
from synapse.persistence import read_schema

from synapse.server import HomeServer

from twisted.internet import reactor
from twisted.enterprise import adbapi
from twisted.python.log import PythonLoggingObserver
from synapse.util.http import TwistedHttpServer, TwistedHttpClient

import argparse
import logging
import sqlite3


logger = logging.getLogger(__name__)


class SynapseHomeServer(HomeServer):
    def build_http_server(self):
        return TwistedHttpServer()

    def build_http_client(self):
        return TwistedHttpClient()

    def build_db_pool(self):
        """ Set up all the dbs. Since all the *.sql have IF NOT EXISTS, so we
        don't have to worry about overwriting existing content.
        """
        logging.info("Preparing database: %s...", self.db_name)
        pool = adbapi.ConnectionPool(
            'sqlite3', self.db_name, check_same_thread=False,
            cp_min=1, cp_max=1)

        schemas = [
                "transactions",
                "pdu",
                "users",
                "profiles",
                "im"
        ]

        for sql_loc in schemas:
            sql_script = read_schema(sql_loc)

            with sqlite3.connect(self.db_name) as db_conn:
                c = db_conn.cursor()
                c.executescript(sql_script)
                c.close()
                db_conn.commit()

        return pool


def setup_logging(verbosity=0, filename=None, config_path=None):
    """ Sets up logging with verbosity levels.

    Args:
        verbosity: The verbosity level.
        filename: Log to the given file rather than to the console.
        config_path: Path to a python logging config file.
    """

    if config_path is None:
        if verbosity == 0:
            level = logging.WARNING
        elif verbosity == 1:
            level = logging.INFO
        else:
            level = logging.DEBUG

        logging.basicConfig(level=level, filename=filename)
    else:
        logging.config.fileConfig(config_path)

    observer = PythonLoggingObserver()
    observer.start()


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("-p", "--port", dest="port", type=int, default=8080,
                        help="The port to listen on.")
    parser.add_argument("-d", "--database", dest="db", default="homeserver.db",
                        help="The database name.")
    parser.add_argument("-H", "--host", dest="host", default="localhost",
                        help="The hostname of the server.")
    parser.add_argument('-v', '--verbose', dest="verbose", action='count',
                        help="The verbosity level.")
    args = parser.parse_args()

    setup_logging(args.verbose)

    logger.info("Server hostname: %s", args.host)

    hs = SynapseHomeServer(args.host,
            db_name=args.db)

    # This object doesn't need to be saved because it's set as the handler for
    # the replication layer
    hs.get_federation()

    hs.register_servlets()

    hs.get_http_server().start_listening(args.port)

    reactor.run()


if __name__ == '__main__':
    run()
