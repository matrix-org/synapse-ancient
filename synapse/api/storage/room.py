# -*- coding: utf-8 -*-
from twisted.internet import defer

from sqlite3 import IntegrityError

from synapse.api.errors import StoreError
from synapse.persistence.tables import RoomMemberTable, RoomsTable

from ._base import SQLBaseStore

import json


class RoomStore(SQLBaseStore):

    def __init__(self, hs):
        super(RoomStore, self).__init__(hs)

    def _insert_room_and_member(self, txn, room_id, room_creator, is_public):
        # create room
        query = ("INSERT INTO " + RoomsTable.table_name +
                    "(room_id, creator, is_public) VALUES(?,?,?)")
        logger.debug("insert_room_and_member %s  room=%s" % (query, room_id))
        txn.execute(query, [room_id, room_creator, is_public])

        # auto join the creator
        query = ("INSERT INTO " + RoomMemberTable.table_name +
                "(user_id, room_id, membership, content) VALUES(?,?,?,?)")
        logger.debug("insert_room_and_member %s  room=%s" % (query, room_id))
        content = json.dumps({"membership": "join"})
        txn.execute(query, [room_creator, room_id, "join", content])

    @defer.inlineCallbacks
    def store_room_and_member(self, room_id=None, room_creator_user_id=None,
                   is_public=None):
        """Stores a room.

        Args:
            room_id (str): The desired room ID, can be None.
            room_creator_user_id (str): The user ID of the room creator.
            is_public (bool): True to indicate that this room should appear in
            public room lists.
        Raises:
            StoreError if the room could not be stored.
        """
        try:
            yield self._db_pool.runInteraction(
                    self._insert_room_and_member, room_id,
                    room_creator_user_id, is_public)
        except IntegrityError:
            raise StoreError(409, "Room ID in use.")
        except Exception as e:
            logger.error("store_room with room_id=%s failed: %s" % (room_id, e))
            raise StoreError(500, "Problem creating room.")

    @defer.inlineCallbacks
    def get_room(self, room_id):
        """Retrieve a room.

        Args:
            room_id (str): The ID of the room to retrieve.
        Returns:
            A namedtuple containing the room information, or an empty list.
        """
        query = RoomsTable.select_statement("room_id=?")
        res = yield self._db_pool.runInteraction(self.exec_single_with_result,
                query, RoomsTable.decode_results, room_id)
        if res:
            defer.returnValue(res[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def get_public_rooms(self):
        """Retrieve a list of all public rooms.

        Returns:
            A list of room dicts containing at least a "room_id" key.
        """
        pass
