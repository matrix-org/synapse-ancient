# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.transactions import run_interaction
from synapse.persistence.tables import (RoomDataTable, RoomMemberTable,
                                        MessagesTable)

import json


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
    cursor = txn.execute(query, args)
    return func(cursor)


def exec_single(txn, query, *args):
    """Runs a single query, returning nothing."""
    txn.execute(query, args)


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
    def store_room_member(self, user_id=None, room_id=None, content=None):
        membership = content["membership"]
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


class EventStore(RoomPathStore, RoomMemberStore, MessageStore):

    def __init__(self):
        super(EventStore, self).__init__()