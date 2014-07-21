# -*- coding: utf-8 -*-
from twisted.internet import defer

from sqlite3 import IntegrityError

from synapse.api.errors import StoreError
from synapse.persistence.transactions import run_interaction
from synapse.util import stringutils
from synapse.persistence.tables import (RoomDataTable, RoomMemberTable,
                                        MessagesTable, RoomsTable)

import json
import logging
import time

logger = logging.getLogger(__name__)


def exec_single_with_result(txn, query, func, *args):
    """Runs a single query for a result set.

    Args:
        txn - Cursor transaction
        query - The query string to execute
        func - The function which can resolve the cursor results to something
        meaningful.
        *args - Query args.
    Returns:
        The result of func(results)
    """
    logger.debug("[SQL] %s  Args=%s Func=%s.%s" % (query, args,
                                                        func.im_self.__name__,
                                                        func.__name__))
    cursor = txn.execute(query, args)
    return func(cursor)


def exec_single(txn, query, *args):
    """Runs a single query, returning nothing."""
    logger.debug("[SQL] %s  Args=%s" % (query, args))
    txn.execute(query, args)


class RegistrationStore(object):

    def __init__(self):
        super(RegistrationStore, self).__init__()

    @defer.inlineCallbacks
    def register(self, user_id, token):
        """Attempts to register an account.

        Args:
            user_id (str): The desired user ID to register.
            token (str): The desired access token to use for this user.
        Raises:
            StoreError if the user_id could not be registered.
        """
        yield run_interaction(self._register, user_id, token)

    def _register(self, txn, user_id, token):
        now = int(time.time())

        try:
            txn.execute("INSERT INTO users(name, creation_ts) VALUES (?,?)",
                        [user_id, now])
        except IntegrityError:
            raise StoreError(400, "User ID already taken.")

        # it's possible for this to get a conflict, but only for a single user
        # since tokens are namespaced based on their user ID
        txn.execute("INSERT INTO access_tokens(user_id, token) " +
                    "VALUES (?,?)", [txn.lastrowid, token])

    @defer.inlineCallbacks
    def get_user(self, token=None):
        """Get a user from the given access token.

        Args:
            token (str): The access token of a user.
        Returns:
            The user ID of the user.
        Raises:
            StoreError if no user was found.
        """
        user_id = yield run_interaction(
                    self._query_for_auth,
                    token)
        defer.returnValue(user_id)

    def _query_for_auth(self, txn, token):
        txn.execute("SELECT users.name FROM access_tokens LEFT JOIN users" +
                    " ON users.id = access_tokens.user_id WHERE token = ?",
                    token)
        row = txn.fetchone()
        if row:
            return row[0]

        raise StoreError()


class RoomStore(object):

    def __init__(self):
        super(RoomStore, self).__init__()

    def _insert_room_and_member(self, txn, room_id, room_creator, is_public):
        # create room
        query = ("INSERT INTO " + RoomsTable.table_name +
                    "(room_id, creator, is_public) VALUES(?,?,?)")
        logger.debug("insert_room_and_member %s  room=%s" % (query, room_id))
        txn.execute(query, [room_id, room_creator, is_public])

        # auto join the creator
        query = ("INSERT INTO " + RoomMemberTable.table_name +
                "(user_id, room_id, membership, content) VALUES(?,?,?,?)")
        logger.debug("insert_room_and_member %s  room=%s" % (query, room_id))
        content = json.dumps({"membership": "join"})
        txn.execute(query, [room_creator, room_id, "join", content])

    @defer.inlineCallbacks
    def store_room(self, room_id=None, room_creator_user_id=None,
                   is_public=None):
        """Stores a room.

        If room_id is None, a randomly generated room ID will be used to store
        this room.

        Args:
            room_id : The desired room ID, can be None.
            room_creator_user_id : The user ID of the room creator.
            is_public : True to indicate that this room should appear in public
            room lists.
        Returns:
            The room ID of the room stored, or None if the room was not stored
            due to a conflict (room_id in use).
        Raises:
            StoreError if the room could not be stored due to an operational
            error (e.g. db access error).
        """
        try:
            if room_id:
                try:
                    yield run_interaction(self._insert_room_and_member, room_id,
                                      room_creator_user_id, is_public)
                except IntegrityError:
                    defer.returnValue(None)
                defer.returnValue(room_id)
            else:
                # autogen room IDs and try to create it. We may clash, so just
                # try a few times till one goes through, giving up eventually.
                attempts = 0
                while attempts < 5:
                    try:
                        gen_room_id = stringutils.random_string(18)
                        yield run_interaction(self._insert_room_and_member,
                                      gen_room_id, room_creator_user_id,
                                      is_public)
                        defer.returnValue(gen_room_id)
                    except IntegrityError:
                        attempts += 1
                raise StoreError()
        except Exception as e:
            logger.error("store_room with room_id=%s failed: %s" % (room_id, e))
            raise StoreError()

    @defer.inlineCallbacks
    def get_room(self, room_id):
        """Retrieve a room.

        Args:
            room_id : The ID of the room to retrieve.
        Returns:
            A namedtuple containing the room information, or an empty list.
        """
        query = RoomsTable.select_statement("room_id=?")
        res = yield run_interaction(exec_single_with_result, query,
                                    RoomsTable.decode_results, room_id)
        defer.returnValue(res)

    @defer.inlineCallbacks
    def get_public_rooms(self):
        """Retrieve a list of all public rooms.

        Returns:
            A list of room dicts containing at least a "room_id" key.
        """
        pass


class MessageStore(object):

    def __init__(self):
        super(MessageStore, self).__init__()

    @defer.inlineCallbacks
    def get_message(self, user_id=None, room_id=None, msg_id=None):
        query = MessagesTable.select_statement(
                "user_id = ? AND room_id = ? AND msg_id = ? " +
                "ORDER BY id DESC LIMIT 1")
        res = yield run_interaction(exec_single_with_result, query,
                                    MessagesTable.decode_results,
                                    user_id, room_id, msg_id)
        defer.returnValue(res)

    @defer.inlineCallbacks
    def store_message(self, user_id=None, room_id=None, msg_id=None,
                      content=None):
        query = ("INSERT INTO " + MessagesTable.table_name +
                 "(user_id, room_id, msg_id, content) VALUES(?,?,?,?)")
        yield run_interaction(exec_single, query, user_id, room_id, msg_id,
                              content)


class RoomMemberStore(object):

    def __init__(self):
        super(RoomMemberStore, self).__init__()

    @defer.inlineCallbacks
    def get_room_member(self, user_id=None, room_id=None):
        query = RoomMemberTable.select_statement(
            "room_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1")
        res = yield run_interaction(exec_single_with_result, query,
                                    RoomMemberTable.decode_results,
                                    room_id, user_id)
        defer.returnValue(res)

    @defer.inlineCallbacks
    def store_room_member(self, user_id=None, room_id=None, membership=None,
                          content=None):
        content_json = json.dumps(content)
        query = ("INSERT INTO " + RoomMemberTable.table_name +
                "(user_id, room_id, membership, content) VALUES(?,?,?,?)")
        yield run_interaction(exec_single, query, user_id, room_id,
                              membership, content_json)


class RoomPathStore(object):

    """Provides various CRUD operations for Room Events. """

    def __init__(self):
        super(RoomPathStore, self).__init__()

    @defer.inlineCallbacks
    def get_path_data(self, path):
        """Retrieve the data stored at this URL path.

        Args:
            path - The url path with something stored.
        Returns:
            The data as JSON or None if nothing exists at this path.
        """
        query = RoomDataTable.select_statement(
            "path = ? ORDER BY id DESC LIMIT 1")
        res = yield run_interaction(exec_single_with_result, query,
                                    RoomDataTable.decode_results, path)
        defer.returnValue(res)

    @defer.inlineCallbacks
    def store_path_data(self, path=None, room_id=None, content=None):
        """Stores path specific data.

        Args:
            path - The path where the data can be retrieved later.
            data - The data to store for this path in JSON.
        """
        query = ("INSERT INTO " + RoomDataTable.table_name +
                "(path, room_id, content) VALUES (?,?,?)")
        yield run_interaction(exec_single, query, path, room_id, content)


class DataStore(RoomPathStore, RoomMemberStore, MessageStore, RoomStore,
                 RegistrationStore):

    def __init__(self):
        super(DataStore, self).__init__()