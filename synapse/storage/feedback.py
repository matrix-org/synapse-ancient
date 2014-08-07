# -*- coding: utf-8 -*-
from synapse.persistence.tables import FeedbackTable

from ._base import SQLBaseStore


def last_row_id(cursor):
    return cursor.lastrowid


class FeedbackStore(SQLBaseStore):

    def store_feedback(self, txn, room_id, msg_id, msg_sender_id,
                       fb_sender_id, fb_type, content):
        query = ("INSERT INTO " + FeedbackTable.table_name +
                 "(room_id, msg_id, msg_sender_id, fb_sender_id, " +
                 "feedback_type, content) VALUES(?,?,?,?,?,?)")
        return self.exec_single_with_result(
            txn, query, last_row_id, room_id, msg_id, msg_sender_id,
            fb_sender_id, fb_type, content
        )

    def get_feedback(self, txn, room_id, msg_id, msg_sender_id,
                     fb_sender_id, fb_type):
        query = FeedbackTable.select_statement(
            "msg_sender_id = ? AND room_id = ? AND msg_id = ? " +
            "AND fb_sender_id = ? AND feedback_type = ? " +
            "ORDER BY id DESC LIMIT 1")
        res = self.exec_single_with_result(
            txn, query, FeedbackTable.decode_results, msg_sender_id, room_id,
            msg_id, fb_sender_id, fb_type
        )
        if res:
            return res[0]
        return None

    def get_max_feedback_id(self, txn):
        return self._simple_max_id(txn, FeedbackTable.table_name)
