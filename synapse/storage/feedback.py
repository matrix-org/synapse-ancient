# -*- coding: utf-8 -*-
from ._base import SQLBaseStore, Table

import collections

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

    EntryType = collections.namedtuple("FeedbackEntry", fields)

