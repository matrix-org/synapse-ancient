# -*- coding: utf-8 -*-
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                    RoomMemberEvent)


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
            return self._event_list[etype](**kwargs)
        except KeyError:  # unknown event type
            # TODO allow custom event types.
            raise NotImplementedError("Unknown etype=%s" % etype)
