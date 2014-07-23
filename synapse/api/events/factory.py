# -*- coding: utf-8 -*-
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                    RoomMemberEvent)

from synapse.util.stringutils import random_string


class EventFactory(object):

    _event_classes = [
        RoomTopicEvent,
        MessageEvent,
        RoomMemberEvent
    ]

    def __init__(self):
        self._event_list = {}  # dict of TYPE to event class
        for event_class in EventFactory._event_classes:
            self._event_list[event_class.TYPE] = event_class

    def create_event(self, etype=None, **kwargs):
        try:
            kwargs["type"] = etype
            if "event_id" not in kwargs:
                kwargs["event_id"] = random_string(10)
            return self._event_list[etype](**kwargs)
        except KeyError:  # unknown event type
            # TODO allow custom event types.
            raise NotImplementedError("Unknown etype=%s" % etype)
