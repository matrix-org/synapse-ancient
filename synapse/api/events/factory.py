# -*- coding: utf-8 -*-
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                    RoomMemberEvent)


class EventFactory(object):

    def __init__(self):
        pass

    def create_event(self, etype=None, **kwargs):
        if etype == RoomTopicEvent.TYPE:
            return RoomTopicEvent(**kwargs)
        elif etype == MessageEvent.TYPE:
            return MessageEvent(**kwargs)
        elif etype == RoomMemberEvent.TYPE:
            return RoomMemberEvent(**kwargs)
        else:
            raise NotImplementedError("Unknown etype=%s" % etype)