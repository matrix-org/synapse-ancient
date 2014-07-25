# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import RoomMemberTable, MessagesTable

from ._base import SQLBaseStore

import logging

logger = logging.getLogger(__name__)


class StreamStore(SQLBaseStore):

    @defer.inlineCallbacks
    def get_message_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0):
        """Get all messages for this user between the given keys.

        Args:
            user_id (str): The user who is requesting messages.
            from_key (int): The ID to start returning results from (exclusive).
            to_key (int): The ID to stop returning results (exclusive).
            room_id (str): Gets messages only for this room. Can be None, in
            which case all room messages will be returned.
        Returns:
            A tuple of rows (list of namedtuples), new_id(int)
        """
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_message_rows, user_id, from_key, to_key, room_id,
                limit)
        defer.returnValue((rows, pkey))

    def _get_message_rows(self, txn, user_id, from_pkey, to_pkey, room_id,
                          limit):
        # work out which rooms this user is joined in on and join them with
        # the room id on the messages table, bounded by the specified pkeys

        # get all messages where the *current* membership state is 'join' for
        # this user in that room.
        query = ("SELECT messages.* FROM messages WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = messages.room_id ORDER BY id DESC LIMIT 1)")
        query_args = ["join", user_id]

        if room_id:
            query += " AND messages.room_id=?"
            query_args.append(room_id)

        LATEST_ROW = -1
        # e.g. if from==to (from=5 to=5 or from=-1 to=-1) then return nothing.
        if from_pkey == to_pkey:
            return ([], from_pkey)
        elif to_pkey > from_pkey:
            if from_pkey != LATEST_ROW:
                # e.g. from=5 to=9 >> from 5 to 9 >> id>5 AND id<9
                query += " AND messages.id > ? AND messages.id < ?"
                query_args.append(from_pkey)
                query_args.append(to_pkey)
            else:
                # e.g. from=-1 to=5 >> from now to 5 >> id>5 ORDER BY id DESC
                query += " AND messages.id > ? ORDER BY id DESC"
                query_args.append(to_pkey)
        elif from_pkey > to_pkey:
            if to_pkey != LATEST_ROW:
                # from=9 to=5 >> from 9 to 5 >> id>5 AND id<9 ORDER BY id DESC
                query += (" AND messages.id > ? AND messages.id < ? " +
                         "ORDER BY id DESC")
                query_args.append(to_pkey)
                query_args.append(from_pkey)
            else:
                # from=5 to=-1 >> from 5 to now >> id>5
                query += " AND messages.id > ?"
                query_args.append(from_pkey)

        if limit and limit > 0:
            query += " LIMIT ?"
            query_args.append(str(limit))

        logger.debug("[SQL] %s : %s" % (query, query_args))
        cursor = txn.execute(query, query_args)
        return self._as_events(cursor, MessagesTable, from_pkey)

    @defer.inlineCallbacks
    def get_room_member_stream(self, user_id=None, from_key=None, to_key=None):
        """Get all room membership events for this user between the given keys.

        Args:
            user_id (str): The user who is requesting membership events.
            from_key (int): The ID to start returning results from (exclusive).
            to_key (int): The ID to stop returning results (exclusive).
        Returns:
            A tuple of rows (list of namedtuples), new_id(int)
        """
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_room_member_rows, user_id, from_key, to_key)
        defer.returnValue((rows, pkey))

    def _get_room_member_rows(self, txn, user_id, from_pkey, to_pkey):
        # get all room membership events for rooms which the user is *currently*
        # joined in on, or all invite events for this user.
        current_membership_sub_query = ("(SELECT membership from " +
                     "room_memberships WHERE user_id=? AND " +
                     "room_id = rm.room_id ORDER BY id DESC " +
                     "LIMIT 1)")

        query = ("SELECT rm.* FROM room_memberships rm WHERE " +
                # all membership events for rooms you're currently joined in on.
                "(? IN " + current_membership_sub_query + " OR " +
                # all invite membership events for this user
                "rm.membership=? AND user_id=?)"
                " AND rm.id > ?")
        query_args = ["join", user_id, "invite", user_id, from_pkey]

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
