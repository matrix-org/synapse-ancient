# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.transactions import run_interaction
from synapse.persistence.tables import RoomDataTable


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


class RoomPathStore(object):

    """Provides various CRUD operations for Room Events. """

    def __init__(self):
        pass

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


class EventStore(RoomPathStore):

    def __init__(self):
        super(EventStore, self).__init__()