# -*- coding: utf-8 -*-
from synapse.types import UserID
from synapse.api.constants import Membership
from synapse.persistence.tables import RoomMemberTable

from ._base import SQLBaseStore

import json
import logging


logger = logging.getLogger(__name__)


def last_row_id(cursor):
    return cursor.lastrowid


class RoomMemberStore(SQLBaseStore):

    def get_room_member(self, txn, user_id, room_id):
        """Retrieve the current state of a room member.

        Args:
            user_id (str): The member's user ID.
            room_id (str): The room the member is in.
        Returns:
            namedtuple: The room member from the database, or None if this
            member does not exist.
        """
        query = RoomMemberTable.select_statement(
            "room_id = ? AND user_id = ? ORDER BY id DESC LIMIT 1")
        res = self.exec_single_with_result(
            txn, query, RoomMemberTable.decode_results, room_id, user_id
        )
        if res:
            return res[0]
        return None

    def store_room_member(self, txn, user_id, sender, room_id, membership,
                          content):
        """Store a room member in the database.

        Args:
            user_id (str): The member's user ID.
            room_id (str): The room in relation to the member.
            membership (synapse.api.constants.Membership): The new membership
            state.
            content (dict): The content of the membership (JSON).
        """

        content_json = json.dumps(content)
        query = ("INSERT INTO " + RoomMemberTable.table_name
                 + " (user_id, sender, room_id, membership, content)"
                 + " VALUES(?,?,?,?,?)")
        return self.exec_single_with_result(
            txn, query, last_row_id, user_id, sender, room_id, membership,
            content_json
        )

    def get_room_members(self, txn, room_id, membership):
        """Retrieve the current room member list for a room.

        Args:
            room_id (str): The room to get the list of members.
            membership (synapse.api.constants.Membership): The filter to apply
            to this list, or None to return all members with some state
            associated with this room.
        Returns:
            list of namedtuples representing the members in this room.
        """
        query = ("SELECT *, MAX(id) FROM " + RoomMemberTable.table_name
                 + " WHERE room_id = ? GROUP BY user_id")
        res = self.exec_single_with_result(
            txn, query, self._room_member_decode, room_id
        )
        # strip memberships which don't match
        if membership:
            res = [entry for entry in res if entry.membership == membership]
        return res

    def get_rooms_for_user_where_membership_is(self, txn, user_id,
                                               membership_list):
        """ Get all the rooms for this user where the membership for this user
        matches one in the membership list.

        Args:
            user_id (str): The user ID.
            membership_list (list): A list of synapse.api.constants.Membership
            values which the user must be in.
        Returns:
            A list of dicts with "room_id" and "membership" keys.
        """
        if not membership_list:
            return None

        args = [user_id]
        membership_placeholder = ["membership=?"] * len(membership_list)
        where_membership = "(" + " OR ".join(membership_placeholder) + ")"
        for membership in membership_list:
            args.append(membership)

        query = ("SELECT room_id, membership FROM room_memberships"
                 + " WHERE user_id=? AND " + where_membership
                 + " GROUP BY room_id ORDER BY id DESC")
        return self.exec_single_with_result(
            txn, query, self.cursor_to_dict, *args
        )

    def _room_member_decode(self, cursor):
        results = cursor.fetchall()
        # strip the MAX(id) column from the results so it can be made into
        # a namedtuple (which requires exactly the number of columns of the
        # table)
        entries = [t[0:-1] for t in results]
        return RoomMemberTable.decode_results(entries)

    def get_joined_hosts_for_room(self, txn, room_id):
        query = (
            "SELECT *, MAX(id) FROM " + RoomMemberTable.table_name +
            " WHERE room_id = ? GROUP BY user_id"
        )

        res = self.exec_single_with_result(
            txn, query, self._room_member_decode, room_id
        )

        def host_from_user_id_string(user_id):
            domain = UserID.from_string(entry.user_id, self.hs).domain
            return domain

        # strip memberships which don't match
        hosts = [
            host_from_user_id_string(entry.user_id)
            for entry in res
            if entry.membership == Membership.JOIN
        ]

        logger.debug("Returning hosts: %s from results: %s", hosts, res)

        return hosts

    def get_max_room_member_id(self, txn):
        return self._simple_max_id(txn, RoomMemberTable.table_name)
