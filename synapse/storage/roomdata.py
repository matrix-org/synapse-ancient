# -*- coding: utf-8 -*-
from synapse.persistence.tables import RoomDataTable

from ._base import SQLBaseTransaction


def last_row_id(cursor):
    return cursor.lastrowid


class RoomDataTransaction(SQLBaseTransaction):
    """Provides various CRUD operations for Room Events. """

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
        res = self.exec_single_with_result(
            query, RoomDataTable.decode_results, room_id, etype, state_key
        )
        if res:
            return res[0]
        return None

    def store_room_data(self, room_id, etype, state_key="", content=None):
        """Transactions room specific data.

        Args:
            room_id (str)
            etype (str)
            state_key (str)
            data (str)- The data to store for this path in JSON.
        Returns:
            The store ID for this data.
        """
        query = ("INSERT INTO " + RoomDataTable.table_name
                 + "(type, state_key, room_id, content) VALUES (?,?,?,?)")
        return self.exec_single_with_result(
            query, last_row_id, etype, state_key, room_id, content
        )

    def get_max_room_data_id(self):
        return self._simple_max_id(RoomDataTable.table_name)
