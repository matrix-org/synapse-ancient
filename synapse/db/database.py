from twistar.registry import Registry

from twisted.enterprise import adbapi
from twisted.internet import defer, reactor

from synapse.api.messages import Message, RoomMembership

import os
import sqlite3


class Database(object):

    def __init__(self, db_name):
        self._db_pool = adbapi.ConnectionPool(
            'sqlite3',
            db_name,
            check_same_thread=False)
        self.db_name = db_name

    def make_default_db_pool(self):
        """ Makes this the default db pool to use when saving Twistar objects.
        """
        Registry.DBPOOL = self._db_pool

    def init_from_file(self, schema_file_path, db_name):
        """ Creates a database using the given schema to the given db_path.

        Args:
            schema_file_path: The path to the .sql
            db_name : The place to store the resulting .db file
        Returns:
            A deferred which will callback iff the database was setup correctly.
        """
        d = defer.Deferred()
        reactor.callLater(0, _setup_db, d, schema_file_path, db_name)
        return d

    def execute_statements(self, statements):
        """ Executes one or more SQL statements as-is.

        Args:
            statements : A string containing the statements to execute.
        Raises:
            If the statements are malformed.
        """
        _execute(self.db_name, statements)

    def _build_where_version(self, from_version=None, to_version=None):
        """ Builds a where clause for the specified versions.

        Args:
            from_version : The version to start from
            to_version : The version to end up at.
        Returns:
            A dict with keys "where", "params", "orderby" whose values can be
            used with DBObject.find : E.g.
            {
              "where" : "id < ? AND id > ?",
              "params" : [from_version, to_version]
              "orderby" : "id ASC"
            }
        """

        # sanity check
        if not from_version and to_version:
            raise IndexError("Cannot have to version without from version.")

        orderby = "id ASC"
        min_ver = from_version
        max_ver = to_version
        where = "1"
        where_arr = []
        if from_version > to_version and to_version is not None:
            # going backwards
            orderby = "id DESC"
            min_ver = to_version
            max_ver = from_version

        if from_version:
            where += " AND id > ?"
            where_arr.append(min_ver)
        if to_version:
            where += " AND id < ?"
            where_arr.append(max_ver)

        return {"where": where, "params": where_arr, "orderby": orderby}

    def get_messages(self, room_id=None, from_version=None, to_version=None,
                     **kwargs):
        where_dict = self._build_where_version(from_version, to_version)
        if room_id:
            where_dict["where"] += " AND room_id = ?"
            where_dict["params"].append(room_id)

        where_arr = [where_dict["where"]] + where_dict["params"]
        return Message.find(
            where=where_arr,
            orderby=where_dict["orderby"],
            **kwargs
        )

    def get_room_membership(self, room_id=None, synid=None):
        """ Retrieves the latest RoomMembership for the given room member.

        Args:
            room_id : The room the member is in
            synid : The member's ID
        Returns:
            The RoomMembership or None.
        """
        if not room_id or not synid:
            return None

        return RoomMembership.find(
            where=["synid=? AND room_id=?", synid, room_id],
            limit=1,
            orderby="id DESC"
        )

    def store_message(self, message):
        pass


def _setup_db(deferred, schema_file_path, db_name):
    """ Creates a sqlite3 db and executes a schema.

    Args:
        deferred: The Deferred for calling back. The result will be True iff
                  the schema was executed, False if the .db already exists.
                  Result will be an Exception on errback.
        schema_file_path: The path to the schema.sql
        db_name: The path to store the .db file
    """
    try:
        if os.path.exists(db_name):
            # assume it is valid
            deferred.callback(False)
            return

        statements = ""
        with open(schema_file_path) as schema:
            statements = schema.read()

        _execute(db_name, statements)
        deferred.callback(True)
    except Exception as e:
        deferred.errback(e)


def _execute(db_name, statements):
    db_conn = sqlite3.connect(db_name)
    cursor = db_conn.cursor()
    try:
        if not sqlite3.complete_statement(statements):
            raise SyntaxError(
                "The provided statements are syntactically incorrect."
            )
        cursor.executescript(statements)
        db_conn.commit()
        db_conn.close()
    except Exception as e:
        cursor.close()
        raise e

