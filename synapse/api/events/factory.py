# -*- coding: utf-8 -*-
from synapse.api.events.room import RoomTopicEvent, MessageEvent


class EventFactory(object):

    def __init__(self):
        pass

    def create_event(self, etype=None, content=None, **kwargs):
        if etype == "sy.room.topic":
            return RoomTopicEvent(content, etype=etype, **kwargs)
        elif etype == "sy.room.message":
            return MessageEvent(content, **kwargs)
        else:
            raise NotImplementedError("Unknown etype=%s" % etype)