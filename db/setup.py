# -*- coding: utf-8 -*-

import sqlite3


class DatabaseSetup(object):
    """ Set's up the database ready for usage.
    """

    def run_setup(db_name):
        DatabaseSetup._pdu_layer(db_name)
        DatabaseSetup._transaction_layer(db_name)

    def _pdu_layer(db_name):
        with open("schema/pdu.sql", "r") as sql_file:
            sql_script = sql_file.read()

        with sqlite3.connect(db_name) as db_conn:
            c = db_conn.cursor()

            c.execute("DROP TABLE IF EXISTS pdus")
            c.execute("DROP TABLE IF EXISTS metadata_pdu")
            c.executescript(sql_script)

            c.close()
            db_conn.commit()

    def _transaction_layer(db_name):
        with open("schema/transactions.sql", "r") as sql_file:
            sql_script = sql_file.read()

        with sqlite3.connect(db_name) as db_conn:
            c = db_conn.cursor()

            c.execute("DROP TABLE IF EXISTS transactions")
            c.executescript(sql_script)

            c.close()
            db_conn.commit()