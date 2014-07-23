# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import MessagesTable

from ._base import SQLBaseStore


class MessageStore(object):

    def __init__(self, hs):
        super(MessageStore, self).__init__(hs)

    @defer.inlineCallbacks
    def get_message(self, user_id=None, room_id=None, msg_id=None):
        query = MessagesTable.select_statement(
                "user_id = ? AND room_id = ? AND msg_id = ? " +
                "ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(exec_single_with_result, query,
                    MessagesTable.decode_results, user_id, room_id, msg_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_message(self, user_id=None, room_id=None, msg_id=None,
                      content=None):
        query = ("INSERT INTO " + MessagesTable.table_name +
                 "(user_id, room_id, msg_id, content) VALUES(?,?,?,?)")
        last_id = yield self._db_pool.runInteraction(
                        exec_single_with_result,
                        query, last_row_id, user_id, room_id,
                        msg_id, content)
        defer.returnValue(last_id)
