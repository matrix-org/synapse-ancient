# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import RoomMemberTable

from ._base import SQLBaseStore

import json


class RoomMemberStore(SQLBaseStore):

    def __init__(self, hs):
        super(RoomMemberStore, self).__init__(hs)

    @defer.inlineCallbacks
    def get_room_member(self, user_id=None, room_id=None):
        query = RoomMemberTable.select_statement(
            "room_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1")
        res = yield self._db_pool.runInteraction(self.exec_single_with_result,
                query, RoomMemberTable.decode_results, room_id, user_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(res)

    @defer.inlineCallbacks
    def store_room_member(self, user_id=None, room_id=None, membership=None,
                          content=None):
        content_json = json.dumps(content)
        query = ("INSERT INTO " + RoomMemberTable.table_name +
                "(user_id, room_id, membership, content) VALUES(?,?,?,?)")
        yield self._db_pool.runInteraction(self.exec_single,
                query, user_id, room_id, membership, content_json)

    @defer.inlineCallbacks
    def get_room_members(self, room_id=None, membership=None):
        query = ("SELECT *, MAX(id) FROM " + RoomMemberTable.table_name +
            " WHERE room_id = ? GROUP BY user_id")
        res = yield self._db_pool.runInteraction(self.exec_single_with_result,
                query, self._room_member_decode, room_id)
        # strip memberships which don't match
        if membership:
            res = [entry for entry in res if entry.membership == membership]
        defer.returnValue(res)

    def _room_member_decode(self, cursor):
        results = cursor.fetchall()
        # strip the MAX(id) column from the results so it can be made into
        # a namedtuple (which requires exactly the number of columns of the
        # table)
        entries = [t[0:-1] for t in results]
        return RoomMemberTable.decode_results(entries)
