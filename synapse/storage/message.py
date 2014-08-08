# -*- coding: utf-8 -*-
from ._base import SQLBaseStore, Table
from synapse.api.events.room import MessageEvent

import collections
import json


class MessageStore(SQLBaseStore):

    def get_message(self, user_id, room_id, msg_id):
        """Get a message from the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
        """
        query = MessagesTable.select_statement(
            "user_id = ? AND room_id = ? AND msg_id = ? " +
            "ORDER BY id DESC LIMIT 1")
        return self._execute(
            MessagesTable.decode_single_result,
            query, user_id, room_id, msg_id,
        )

    def store_message(self, user_id, room_id, msg_id, content):
        """Store a message in the store.

        Args:
            user_id (str): The ID of the user who sent the message.
            room_id (str): The room the message was sent in.
            msg_id (str): The unique ID for this user/room combo.
            content (str): The content of the message (JSON)
        """
        return self._simple_insert(MessagesTable.table_name, dict(
            user_id=user_id,
            room_id=room_id,
            msg_id=msg_id,
            content=content,
        ))

    def get_max_message_id(self):
        return self._simple_max_id(MessagesTable.table_name)


class MessagesTable(Table):
    table_name = "messages"

    fields = [
        "id",
        "user_id",
        "room_id",
        "msg_id",
        "content"
    ]

    class EntryType(collections.namedtuple("MessageEntry", fields)):

        def as_event(self, event_factory):
            return event_factory.create_event(
                etype=MessageEvent.TYPE,
                room_id=self.room_id,
                user_id=self.user_id,
                msg_id=self.msg_id,
                content=json.loads(self.content),
            )
