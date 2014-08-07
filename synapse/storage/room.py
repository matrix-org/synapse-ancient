# -*- coding: utf-8 -*-
from sqlite3 import IntegrityError

from synapse.api.errors import StoreError
from synapse.api.events.room import RoomTopicEvent
from synapse.persistence.tables import RoomsTable

from ._base import SQLBaseStore

import json
import logging

logger = logging.getLogger(__name__)


class RoomStore(SQLBaseStore):

    def _insert_room(self, txn, room_id, room_creator, is_public):
        # create room
        query = ("INSERT INTO " + RoomsTable.table_name
                 + "(room_id, creator, is_public) VALUES(?,?,?)")
        logger.debug("insert_room_and_member %s  room=%s", query, room_id)
        txn.execute(query, [room_id, room_creator, is_public])

    def store_room(self, txn, room_id, room_creator_user_id, is_public):
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
            return self._insert_room(
                txn, room_id, room_creator_user_id, is_public
            )
        except IntegrityError:
            raise StoreError(409, "Room ID in use.")
        except Exception as e:
            logger.error("store_room with room_id=%s failed: %s", room_id, e)
            raise StoreError(500, "Problem creating room.")

    def store_room_config(self, txn, room_id, visibility):
        self._simple_update_one(
            txn=txn,
            table=RoomsTable.table_name,
            keyvalues={"room_id": room_id},
            updatevalues={"is_public": visibility}
        )

    def get_room(self, txn, room_id):
        """Retrieve a room.

        Args:
            room_id (str): The ID of the room to retrieve.
        Returns:
            A namedtuple containing the room information, or an empty list.
        """
        query = RoomsTable.select_statement("room_id=?")
        res = self.exec_single_with_result(
            txn, query, RoomsTable.decode_results, room_id
        )
        if res:
            return res[0]
        return None

    def get_rooms(self, txn, is_public, with_topics):
        """Retrieve a list of all public rooms.

        Args:
            is_public (bool): True if the rooms returned should be public.
            with_topics (bool): True to include the current topic for the room
            in the response.
        Returns:
            A list of room dicts containing at least a "room_id" key, and a
            "topic" key if one is set and with_topic=True.
        """
        room_data_type = RoomTopicEvent.TYPE
        public = 1 if is_public else 0

        latest_topic = ("SELECT max(room_data.id) FROM room_data WHERE "
                        + "room_data.type = ? GROUP BY room_id")

        query = ("SELECT rooms.*, room_data.content FROM rooms LEFT JOIN "
                 + "room_data ON rooms.room_id = room_data.room_id WHERE "
                 + "(room_data.id IN (" + latest_topic + ") "
                 + "OR room_data.id IS NULL) AND rooms.is_public = ?")

        res = self.exec_single_with_result(
            txn, query, self.cursor_to_dict, room_data_type, public
        )

        # return only the keys the specification expects
        ret_keys = ["room_id", "topic"]

        # extract topic from the json (icky) FIXME
        for i, room_row in enumerate(res):
            try:
                content_json = json.loads(room_row["content"])
                room_row["topic"] = content_json["topic"]
            except:
                pass  # no topic set
            # filter the dict based on ret_keys
            res[i] = {k: v for k, v in room_row.iteritems() if k in ret_keys}
