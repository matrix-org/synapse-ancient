# -*- coding: utf-8 -*-
from synapse.api.events.room import (
    RoomTopicEvent, MessageEvent, RoomMemberEvent
)

from . import SynapseEvent, SynapseStateEvent
from .validator import EventValidator

from synapse.util.stringutils import random_string
from synapse.util.logutils import log_function

import time


class EventFactory(object):

    def __init__(self, server_name):
        self.server_name = server_name
        self._validator = EventValidator()

    @log_function
    def create_event(self, etype=None, **kwargs):
        if "event_id" not in kwargs:
            event_id = "%s%s" % (int(time.time() * 1000), random_string(10))
            kwargs["event_id"] = event_id

        if etype == RoomTopicEvent.TYPE:
            event = RoomTopicEvent(**kwargs)
        elif etype == MessageEvent.TYPE:
            event = MessageEvent(**kwargs)
        elif etype == RoomMemberEvent.TYPE:
            event = RoomMemberEvent(**kwargs)
        elif "is_state" in kwargs and kwargs["is_state"]:
            event = SynapseStateEvent(type=etype, **kwargs)
        else:
            event = SynapseEvent(type=etype, **kwargs)

        self._validator.validate(event, event.TEMPLATE, raises=True)

        return event
