# -*- coding: utf-8 -*-
from synapse.persistence.tables import MessagesTable

from ._base import SQLBaseStore


def last_row_id(cursor):
    return cursor.lastrowid


class MessageStore(SQLBaseStore):

    def get_message(self, txn, user_id, room_id, msg_id):
        """Get a message from the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
        """
        query = MessagesTable.select_statement(
            "user_id = ? AND room_id = ? AND msg_id = ? " +
            "ORDER BY id DESC LIMIT 1")
        res = self.exec_single_with_result(
            txn, query, MessagesTable.decode_results, user_id, room_id, msg_id
        )
        if res:
            return res[0]
        return None

    def store_message(self, txn, user_id, room_id, msg_id, content):
        """Store a message in the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
            content (str): The content of the message (JSON)
        """
        query = ("INSERT INTO " + MessagesTable.table_name +
                 "(user_id, room_id, msg_id, content) VALUES(?,?,?,?)")
        return self.exec_single_with_result(
            txn, query, last_row_id, user_id, room_id, msg_id, content
        )

    def get_max_message_id(self, txn):
        return self._simple_max_id(txn, MessagesTable.table_name)
