# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import RoomDataTable

from ._base import SQLBaseStore


class RoomPathStore(SQLBaseStore):

    """Provides various CRUD operations for Room Events. """

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
        res = yield self._db_pool.runInteraction(self.exec_single_with_result,
                query, RoomDataTable.decode_results, path)
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
        yield self._db_pool.runInteraction(self.exec_single, query, path,
                room_id, content)
