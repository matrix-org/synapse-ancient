# -*- coding: utf-8 -*-
from ._base import SQLBaseStore, Table
from synapse.api.events.room import FeedbackEvent

import collections
import json


class FeedbackStore(SQLBaseStore):

    def store_feedback(self, room_id, msg_id, msg_sender_id,
                       fb_sender_id, fb_type, content):
        return self._simple_insert(FeedbackTable.table_name, dict(
            room_id=room_id,
            msg_id=msg_id,
            msg_sender_id=msg_sender_id,
            fb_sender_id=fb_sender_id,
            fb_type=fb_type,
            content=content,
        ))

    def get_feedback(self, room_id=None, msg_id=None, msg_sender_id=None,
                     fb_sender_id=None, fb_type=None):
        query = FeedbackTable.select_statement(
            "msg_sender_id = ? AND room_id = ? AND msg_id = ? " +
            "AND fb_sender_id = ? AND feedback_type = ? " +
            "ORDER BY id DESC LIMIT 1")
        return self._execute(
            FeedbackTable.decode_single_result,
            query, msg_sender_id, room_id, msg_id, fb_sender_id, fb_type,
        )

    def get_max_feedback_id(self):
        return self._simple_max_id(FeedbackTable.table_name)


class FeedbackTable(Table):
    table_name = "feedback"

    fields = [
        "id",
        "content",
        "feedback_type",
        "fb_sender_id",
        "msg_id",
        "room_id",
        "msg_sender_id"
    ]

    class EntryType(collections.namedtuple("FeedbackEntry", fields)):

        def as_event(self, event_factory):
            return event_factory.create_event(
                etype=FeedbackEvent.TYPE,
                room_id=self.room_id,
                msg_id=self.msg_id,
                msg_sender_id=self.msg_sender_id,
                user_id=self.fb_sender_id,
                feedback_type=self.feedback_type,
                content=json.loads(self.content),
            )
