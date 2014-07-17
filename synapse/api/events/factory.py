# -*- coding: utf-8 -*-
from synapse.api.events.room import RoomTopicEvent, MessageEvent


class EventFactory(object):

    def __init__(self):
        pass

    def create_event(self, typ=None, content=None):
        if typ == "sy.room.topic":
            return RoomTopicEvent(content)
        elif typ == "sy.room.message":
            return MessageEvent(content)