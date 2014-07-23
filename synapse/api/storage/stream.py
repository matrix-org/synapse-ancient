# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import RoomMemberTable, MessagesTable

from ._base import SQLBaseStore


class StreamStore(SQLBaseStore):

    def __init__(self, hs):
        super(StreamStore, self).__init__()
        self._db_pool = hs.get_db_pool()

    @defer.inlineCallbacks
    def get_message_stream(self, user_id=None, from_key=None, to_key=None):
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_message_rows, user_id, from_key, to_key)
        defer.returnValue((rows, pkey))

    def _get_message_rows(self, txn, user_id, from_pkey, to_pkey):
        # work out which rooms this user is joined in on and join them with
        # the room id on the messages table, bounded by the specified pkeys

        # get all messages where the *current* membership state is 'join' for
        # this user in that room.
        query = ("SELECT messages.* FROM messages WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = messages.room_id ORDER BY id DESC LIMIT 1) " +
            "AND messages.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND messages.id < ?"
            query_args.append(to_pkey)

        cursor = txn.execute(query, query_args)
        return self._as_events(cursor, MessagesTable, from_pkey)

    @defer.inlineCallbacks
    def get_room_member_stream(self, user_id=None, from_key=None, to_key=None):
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_room_member_rows, user_id, from_key, to_key)
        defer.returnValue((rows, pkey))

    def _get_room_member_rows(self, txn, user_id, from_pkey, to_pkey):
        # get all room membership events for rooms which the user is *currently*
        # joined in on.
        query = ("SELECT rm.* FROM room_memberships rm WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = rm.room_id ORDER BY id DESC LIMIT 1) " +
            "AND rm.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND rm.id < ?"
            query_args.append(to_pkey)

        cursor = txn.execute(query, query_args)
        return self._as_events(cursor, RoomMemberTable, from_pkey)

    def _as_events(self, cursor, table, from_pkey):
        data_entries = table.decode_results(cursor)
        last_pkey = from_pkey
        if data_entries:
            last_pkey = data_entries[-1].id
        events = self.to_events(data_entries)
        return (events, last_pkey)
