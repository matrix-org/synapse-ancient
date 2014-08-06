# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import MessagesTable

from ._base import SQLBaseStore


def last_row_id(cursor):
    return cursor.lastrowid


class MessageStore(SQLBaseStore):

    @defer.inlineCallbacks
    def get_message(self, user_id=None, room_id=None, msg_id=None):
        """Get a message from the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
        """
        query = MessagesTable.select_statement(
            "user_id = ? AND room_id = ? AND msg_id = ? " +
            "ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(
            self.exec_single_with_result,
            query, MessagesTable.decode_results, user_id, room_id, msg_id
        )
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_message(self, user_id=None, room_id=None, msg_id=None,
                      content=None):
        """Store a message in the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
            content (str): The content of the message (JSON)
        """
        query = ("INSERT INTO " + MessagesTable.table_name +
                 "(user_id, room_id, msg_id, content) VALUES(?,?,?,?)")
        last_id = yield self._db_pool.runInteraction(
            self.exec_single_with_result,
            query, last_row_id, user_id, room_id,
            msg_id, content
        )
        defer.returnValue(last_id)

    @defer.inlineCallbacks
    def get_max_message_id(self):
        max_id = yield self._simple_max_id(MessagesTable.table_name)
        defer.returnValue(max_id)
