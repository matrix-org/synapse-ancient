# -*- coding: utf-8 -*-

from synapse.api.errors import StoreError
from synapse.api.events.room import RoomMemberEvent, MessageEvent
from synapse.persistence.tables import RoomMemberTable, MessagesTable

import json

from .message import MessageStore
from .profile import ProfileStore
from .registration import RegistrationStore
from .room import RoomStore
from .roommember import RoomMemberStore
from .roompath import RoomPathStore
from .stream import StreamStore


class DataStore(RoomPathStore, RoomMemberStore, MessageStore, RoomStore,
                 RegistrationStore, StreamStore, ProfileStore):

    def __init__(self, hs):
        super(DataStore, self).__init__(hs)
        self.event_factory = hs.get_event_factory()

    def _create_event(self, store_data):
        event_type = None
        fields = {}
        if store_data.__class__ == RoomMemberTable.EntryType:
            event_type = RoomMemberEvent.TYPE
            fields = {
                "target_user_id": store_data.user_id,
                "content": {"membership": store_data.membership},
                "room_id": store_data.room_id,
                "user_id": store_data.user_id
            }
        elif store_data.__class__ == MessagesTable.EntryType:
            event_type = MessageEvent.TYPE
            fields = {
                "room_id": store_data.room_id,
                "user_id": store_data.user_id,
                "msg_id": store_data.msg_id,
                "content": json.loads(store_data.content)
            }
        else:
            raise StoreError("Cannot map class %s." % store_data.__class__)

        return self.event_factory.create_event(
            etype=event_type,
            **fields
            )

    def to_events(self, store_data_list):
        """Converts a representation of store data into event streamable data.

        This maps the way data is represented from the database into events.

        Args:
            store_data (list): A list of namedtuples received from the store.
        Returns:
            list: A list of dicts which represent these namedtuples as events.
        Raises:
            StoreError if there was a problem parsing these namedtuples.
        """
        events = []
        for d in store_data_list:
            events.append(self._create_event(d).get_dict())
        return events
