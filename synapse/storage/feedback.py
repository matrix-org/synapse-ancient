# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import FeedbackTable

from ._base import SQLBaseStore


def last_row_id(cursor):
    return cursor.lastrowid


class FeedbackStore(SQLBaseStore):

    # @defer.inlineCallbacks
    def store_feedback(self, room_id=None, msg_id=None, msg_sender_id=None,
                       fb_sender_id=None, fb_type=None, content=None):
        print "STORE FEEDBACK %s" % fb_type

    def get_feedback(self, room_id=None, msg_id=None, msg_sender_id=None,
                     fb_sender_id=None, fb_type=None):
        print "GET FEEDBACK %s" % fb_type