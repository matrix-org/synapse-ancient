# -*- coding: utf-8 -*-
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                    RoomMemberEvent)


class EventFactory(object):

    def __init__(self):
        pass

    def create_event(self, etype=None, content=None, **kwargs):
        if etype == RoomTopicEvent.TYPE:
            return RoomTopicEvent(content, **kwargs)
        elif etype == MessageEvent.TYPE:
            return MessageEvent(content, **kwargs)
        elif etype == RoomMemberEvent.TYPE:
            return RoomMemberEvent(content, **kwargs)
        else:
            raise NotImplementedError("Unknown etype=%s" % etype)