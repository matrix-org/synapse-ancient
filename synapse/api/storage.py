# -*- coding: utf-8 -*-
from twisted.internet import defer

from sqlite3 import IntegrityError

from synapse.api.errors import StoreError
from synapse.api.events.room import RoomMemberEvent, MessageEvent
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


class StreamStore(object):

    def __init__(self, hs):
        super(StreamStore, self).__init__()
        self._db_pool = hs.get_db_pool()

    @defer.inlineCallbacks
    def get_message_stream(self, user_id=None, from_key=None, to_key=None):
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_message_rows, user_id, from_key, to_key)
        defer.returnValue((rows, pkey))

    def _get_message_rows(self, txn, user_id, from_pkey, to_pkey):
        # work out which rooms this user is joined in on and join them with
        # the room id on the messages table, bounded by the specified pkeys

        # get all messages where the *current* membership state is 'join' for
        # this user in that room.
        query = ("SELECT messages.* FROM messages WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = messages.room_id ORDER BY id DESC LIMIT 1) " +
            "AND messages.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND messages.id < ?"
            query_args.append(to_pkey)

        txn.execute(query, query_args)

        col_headers = [i[0] for i in txn.description]
        result_set = txn.fetchall()
        data = []
        last_pkey = from_pkey
        for result in result_set:
            result_dict = dict(zip(col_headers, result))
            last_pkey = result_dict["id"]
            result_dict.pop("id")
            if "content" in result_dict:
                result_dict["content"] = json.loads(result_dict["content"])
            result_dict["type"] = MessageEvent.TYPE
            data.append(result_dict)

        return (data, last_pkey)

    @defer.inlineCallbacks
    def get_room_member_stream(self, user_id=None, from_key=None, to_key=None):
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_room_member_rows, user_id, from_key, to_key)
        defer.returnValue((rows, pkey))

    def _get_room_member_rows(self, txn, user_id, from_pkey, to_pkey):
        # get all room membership events for rooms which the user is *currently*
        # joined in on.
        query = ("SELECT rm.* FROM room_memberships rm WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = rm.room_id ORDER BY id DESC LIMIT 1) " +
            "AND rm.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND rm.id < ?"
            query_args.append(to_pkey)

        txn.execute(query, query_args)

        col_headers = [i[0] for i in txn.description]
        result_set = txn.fetchall()
        data = []
        last_pkey = from_pkey
        for result in result_set:
            result_dict = dict(zip(col_headers, result))
            last_pkey = result_dict["id"]
            result_dict.pop("id")
            if "content" in result_dict:
                result_dict["content"] = json.loads(result_dict["content"])
            result_dict["type"] = RoomMemberEvent.TYPE
            data.append(result_dict)

        return (data, last_pkey)


class RegistrationStore(object):

    def __init__(self, hs):
        super(RegistrationStore, self).__init__(hs)

    @defer.inlineCallbacks
    def register(self, user_id, token):
        """Attempts to register an account.

        Args:
            user_id (str): The desired user ID to register.
            token (str): The desired access token to use for this user.
        Raises:
            StoreError if the user_id could not be registered.
        """
        yield self._db_pool.runInteraction(self._register, user_id, token)

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
            str: The user ID of the user.
        Raises:
            StoreError if no user was found.
        """
        user_id = yield self._db_pool.runInteraction(self._query_for_auth,
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

    def __init__(self, hs):
        super(RoomStore, self).__init__(hs)

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
    def store_room_and_member(self, room_id=None, room_creator_user_id=None,
                   is_public=None):
        """Stores a room.

        Args:
            room_id (str): The desired room ID, can be None.
            room_creator_user_id (str): The user ID of the room creator.
            is_public (bool): True to indicate that this room should appear in
            public room lists.
        Raises:
            StoreError if the room could not be stored.
        """
        try:
            yield self._db_pool.runInteraction(
                    self._insert_room_and_member, room_id,
                    room_creator_user_id, is_public)
        except IntegrityError:
            raise StoreError(409, "Room ID in use.")
        except Exception as e:
            logger.error("store_room with room_id=%s failed: %s" % (room_id, e))
            raise StoreError(500, "Problem creating room.")

    @defer.inlineCallbacks
    def get_room(self, room_id):
        """Retrieve a room.

        Args:
            room_id (str): The ID of the room to retrieve.
        Returns:
            A namedtuple containing the room information, or an empty list.
        """
        query = RoomsTable.select_statement("room_id=?")
        res = yield self._db_pool.runInteraction(exec_single_with_result, query,
                    RoomsTable.decode_results, room_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def get_public_rooms(self):
        """Retrieve a list of all public rooms.

        Returns:
            A list of room dicts containing at least a "room_id" key.
        """
        pass


class MessageStore(object):

    def __init__(self, hs):
        super(MessageStore, self).__init__(hs)

    @defer.inlineCallbacks
    def get_message(self, user_id=None, room_id=None, msg_id=None):
        query = MessagesTable.select_statement(
                "user_id = ? AND room_id = ? AND msg_id = ? " +
                "ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(exec_single_with_result, query,
                    MessagesTable.decode_results, user_id, room_id, msg_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_message(self, user_id=None, room_id=None, msg_id=None,
                      content=None):
        query = ("INSERT INTO " + MessagesTable.table_name +
                 "(user_id, room_id, msg_id, content) VALUES(?,?,?,?)")
        yield self._db_pool.runInteraction(exec_single, query, user_id, room_id,
                    msg_id, content)


class RoomMemberStore(object):

    def __init__(self, hs):
        super(RoomMemberStore, self).__init__(hs)

    @defer.inlineCallbacks
    def get_room_member(self, user_id=None, room_id=None):
        query = RoomMemberTable.select_statement(
            "room_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(exec_single_with_result, query,
                    RoomMemberTable.decode_results, room_id, user_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(res)

    @defer.inlineCallbacks
    def store_room_member(self, user_id=None, room_id=None, membership=None,
                          content=None):
        content_json = json.dumps(content)
        query = ("INSERT INTO " + RoomMemberTable.table_name +
                "(user_id, room_id, membership, content) VALUES(?,?,?,?)")
        yield self._db_pool.runInteraction(exec_single, query, user_id, room_id,
                    membership, content_json)


class RoomPathStore(object):

    """Provides various CRUD operations for Room Events. """

    def __init__(self, hs):
        super(RoomPathStore, self).__init__(hs)

    @defer.inlineCallbacks
    def get_path_data(self, path):
        """Retrieve the data stored at this URL path.

        Args:
            path (str)- The url path with something stored.
        Returns:
            namedtuple: Or None if nothing exists at this path.
        """
        query = RoomDataTable.select_statement(
            "path = ? ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(exec_single_with_result, query,
                    RoomDataTable.decode_results, path)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_path_data(self, path=None, room_id=None, content=None):
        """Stores path specific data.

        Args:
            path (str)- The path where the data can be retrieved later.
            data (str)- The data to store for this path in JSON.
        """
        query = ("INSERT INTO " + RoomDataTable.table_name +
                "(path, room_id, content) VALUES (?,?,?)")
        yield self._db_pool.runInteraction(exec_single, query, path, room_id,
                content)


class DataStore(RoomPathStore, RoomMemberStore, MessageStore, RoomStore,
                 RegistrationStore, StreamStore):

    def __init__(self, hs):
        super(DataStore, self).__init__(hs)
