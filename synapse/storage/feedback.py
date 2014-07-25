# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import FeedbackTable

from ._base import SQLBaseStore


def last_row_id(cursor):
    return cursor.lastrowid


class FeedbackStore(SQLBaseStore):

    @defer.inlineCallbacks
    def store_feedback(self, room_id=None, msg_id=None, msg_sender_id=None,
                       fb_sender_id=None, fb_type=None, content=None):
        query = ("INSERT INTO " + FeedbackTable.table_name +
                 "(room_id, msg_id, msg_sender_id, fb_sender_id, " +
                 "feedback_type, content) VALUES(?,?,?,?,?,?)")
        last_id = yield self._db_pool.runInteraction(
                        self.exec_single_with_result,
                        query, last_row_id, room_id, msg_id, msg_sender_id,
                        fb_sender_id, fb_type, content)
        defer.returnValue(last_id)

    @defer.inlineCallbacks
    def get_feedback(self, room_id=None, msg_id=None, msg_sender_id=None,
                     fb_sender_id=None, fb_type=None):
        query = FeedbackTable.select_statement(
                "msg_sender_id = ? AND room_id = ? AND msg_id = ? " +
                "AND fb_sender_id = ? AND feedback_type = ? " +
                "ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(self.exec_single_with_result,
                query, FeedbackTable.decode_results, msg_sender_id, room_id,
                msg_id, fb_sender_id, fb_type)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)