# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.persistence.tables import (RoomMemberTable, MessagesTable,
                                       FeedbackTable)

from ._base import SQLBaseStore

import json
import logging

logger = logging.getLogger(__name__)


class StreamStore(SQLBaseStore):

    @defer.inlineCallbacks
    def get_message_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0, with_feedback=False):
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
        if with_feedback and room_id:  # with fb MUST specify a room ID
            (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_message_rows_with_feedback, user_id, from_key, to_key,
                room_id, limit)
        else:
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

        (query, query_args) = self._append_stream_operations("messages",
                                query, query_args, from_pkey, to_pkey, limit)

        logger.debug("[SQL] %s : %s" % (query, query_args))
        cursor = txn.execute(query, query_args)
        return self._as_events(cursor, MessagesTable, from_pkey)

    def _get_message_rows_with_feedback(self, txn, user_id, from_pkey, to_pkey,
                                        room_id, limit):
        # this col represents the compressed feedback JSON as per spec
        compressed_feedback_col = ("'[' || group_concat('{\"sender_id\":\"' ||"
        " f.fb_sender_id || '\",\"feedback_type\":\"' || f.feedback_type ||"
        " '\",\"content\":' || f.content || '}') || ']'")

        global_msg_id_join = ("f.room_id = messages.room_id and " +
        "f.msg_id = messages.msg_id and messages.user_id = f.msg_sender_id")

        select_query = ("SELECT messages.*, f.content AS fb_content, " +
        "f.fb_sender_id, " + compressed_feedback_col + " AS compressed_fb " +
        "FROM messages LEFT JOIN feedback f ON " + global_msg_id_join)

        current_membership_sub_query = ("(SELECT membership from " +
        "room_memberships rm WHERE user_id=? AND room_id = rm.room_id " +
        "ORDER BY id DESC LIMIT 1)")

        where = (" WHERE ? IN " + current_membership_sub_query + " AND " +
        "messages.room_id=?")

        query = select_query + where + " GROUP BY messages.id"
        query_args = ["join", user_id, room_id]

        logger.debug("[SQL] %s : %s" % (query, query_args))
        cursor = txn.execute(query, query_args)

        # convert the result set into events
        entries = self.cursor_to_dict(cursor)
        events = []
        for entry in entries:
            # TODO we should spec the cursor > event mapping somewhere else.
            event = {}
            straight_mappings = ["msg_id", "user_id", "room_id"]
            for key in straight_mappings:
                event[key] = entry[key]
            event["content"] = json.loads(entry["content"])
            event["feedback"] = json.loads(entry["compressed_fb"])
            events.append(event)

        latest_pkey = from_pkey if len(entries) == 0 else entries[-1]["id"]

        return (events, latest_pkey)

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

    @defer.inlineCallbacks
    def get_feedback_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0):
        (rows, pkey) = yield self._db_pool.runInteraction(
                self._get_feedback_rows, user_id, from_key, to_key, room_id,
                limit)
        defer.returnValue((rows, pkey))

    def _get_feedback_rows(self, txn, user_id, from_pkey, to_pkey, room_id,
                           limit):
        # work out which rooms this user is joined in on and join them with
        # the room id on the feedback table, bounded by the specified pkeys

        # get all messages where the *current* membership state is 'join' for
        # this user in that room.
        query = ("SELECT feedback.* FROM feedback WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = feedback.room_id ORDER BY id DESC LIMIT 1)")
        query_args = ["join", user_id]

        if room_id:
            query += " AND feedback.room_id=?"
            query_args.append(room_id)

        (query, query_args) = self._append_stream_operations("feedback",
                                query, query_args, from_pkey, to_pkey, limit)

        logger.debug("[SQL] %s : %s" % (query, query_args))
        cursor = txn.execute(query, query_args)
        return self._as_events(cursor, FeedbackTable, from_pkey)

    def _append_stream_operations(self, table_name, query, query_args,
                                  from_pkey, to_pkey, limit):
        LATEST_ROW = -1
        # e.g. if from==to (from=5 to=5 or from=-1 to=-1) then return nothing.
        if from_pkey == to_pkey:
            return ([], from_pkey)
        elif to_pkey > from_pkey:
            if from_pkey != LATEST_ROW:
                # e.g. from=5 to=9 >> from 5 to 9 >> id>5 AND id<9
                query += (" AND %s.id > ? AND %s.id < ?" %
                         (table_name, table_name))
                query_args.append(from_pkey)
                query_args.append(to_pkey)
            else:
                # e.g. from=-1 to=5 >> from now to 5 >> id>5 ORDER BY id DESC
                query += " AND %s.id > ? ORDER BY id DESC" % table_name
                query_args.append(to_pkey)
        elif from_pkey > to_pkey:
            if to_pkey != LATEST_ROW:
                # from=9 to=5 >> from 9 to 5 >> id>5 AND id<9 ORDER BY id DESC
                query += (" AND %s.id > ? AND %s.id < ? ORDER BY id DESC" %
                          (table_name, table_name))
                query_args.append(to_pkey)
                query_args.append(from_pkey)
            else:
                # from=5 to=-1 >> from 5 to now >> id>5
                query += " AND %s.id > ?" % table_name
                query_args.append(from_pkey)

        if limit and limit > 0:
            query += " LIMIT ?"
            query_args.append(str(limit))

        return (query, query_args)

    def _as_events(self, cursor, table, from_pkey):
        data_entries = table.decode_results(cursor)
        last_pkey = from_pkey
        if data_entries:
            last_pkey = data_entries[-1].id
        events = self.to_events(data_entries)
        return (events, last_pkey)
