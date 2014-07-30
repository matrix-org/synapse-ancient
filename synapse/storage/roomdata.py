# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import RoomDataTable

from ._base import SQLBaseStore


class RoomDataStore(SQLBaseStore):

    """Provides various CRUD operations for Room Events. """

    @defer.inlineCallbacks
    def get_room_data(self, room_id, etype, state_key=""):
        """Retrieve the data stored under this type and state_key.

        Args:
            room_id (str)
            etype (str)
            state_key (str)
        Returns:
            namedtuple: Or None if nothing exists at this path.
        """
        query = RoomDataTable.select_statement(
            "room_id = ? AND type = ? AND state_key = ? "
            "ORDER BY id DESC LIMIT 1"
        )
        res = yield self._db_pool.runInteraction(
            self.exec_single_with_result,
            query, RoomDataTable.decode_results,
            room_id, etype, state_key
        )
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_room_data(self, room_id, etype, state_key="", content=None):
        """Stores room specific data.

        Args:
            room_id (str)
            etype (str)
            state_key (str)
            data (str)- The data to store for this path in JSON.
        """
        query = ("INSERT INTO " + RoomDataTable.table_name +
                "(type, state_key, room_id, content) VALUES (?,?,?,?)")
        yield self._db_pool.runInteraction(
            self.exec_single, query,
            etype, state_key, room_id, content
        )