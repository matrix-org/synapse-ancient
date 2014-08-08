# -*- coding: utf-8 -*-

from synapse.api.events.room import (
    RoomMemberEvent, MessageEvent, RoomTopicEvent, FeedbackEvent,
    RoomConfigEvent
)

import json

from .feedback import FeedbackStore
from .message import MessageStore
from .presence import PresenceStore
from .profile import ProfileStore
from .registration import RegistrationStore
from .room import RoomStore
from .roommember import RoomMemberStore
from .roomdata import RoomDataStore
from .stream import StreamStore


class DataStore(RoomDataStore, RoomMemberStore, MessageStore, RoomStore,
                RegistrationStore, StreamStore, ProfileStore, FeedbackStore,
                PresenceStore):

    def __init__(self, hs):
        super(DataStore, self).__init__(hs)
        self.event_factory = hs.get_event_factory()
        self.hs = hs

    def persist_event(self, event):
        if event.type == MessageEvent.TYPE:
            return self.store_message(
                user_id=event.user_id,
                room_id=event.room_id,
                msg_id=event.msg_id,
                content=json.dumps(event.content)
            )
        elif event.type == RoomMemberEvent.TYPE:
            return self.store_room_member(
                user_id=event.target_user_id,
                sender=event.user_id,
                room_id=event.room_id,
                content=event.content,
                membership=event.content["membership"]
            )
        elif event.type == FeedbackEvent.TYPE:
            return self.store_feedback(
                room_id=event.room_id,
                msg_id=event.msg_id,
                msg_sender_id=event.msg_sender_id,
                fb_sender_id=event.user_id,
                fb_type=event.feedback_type,
                content=json.dumps(event.content)
            )
        elif event.type == RoomTopicEvent.TYPE:
            return self.store_room_data(
                room_id=event.room_id,
                etype=event.type,
                state_key=event.state_key,
                content=json.dumps(event.content)
            )
        elif event.type == RoomConfigEvent.TYPE:
            if "visibility" in event.content:
                visibility = event.content["visibility"]
                return self.store_room_config(
                    room_id=event.room_id,
                    visibility=visibility
                )

        else:
            raise NotImplementedError(
                "Don't know how to persist type=%s" % event.type
            )
