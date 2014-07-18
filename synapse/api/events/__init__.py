# -*- coding: utf-8 -*-
from synapse.federation.units import JsonEncodedObject

from .validator import SynapseEventTemplate, SynapseEventStateTemplate


class SynapseEvent(JsonEncodedObject):

    """Base class for Synapse events. These are JSON objects which must abide by
    a certain well-defined structure.
    """

    valid_keys = [
        "event_id",
        "room_id",
        "type",
        "content",
        "sender",
        "ts",
        "is_state",
        "state_key",
        "auth_user_id",
        "msg_id",
        "target_user",
        "membership",
    ]

    internal_keys = [
        "auth_user_id",
    ]

    required_keys = [
        "event_id",
        "room_id",
        "type",
        "content",
        "is_state",
    ]

    TEMPLATE = SynapseEventTemplate

    def __init__(self, is_state=False, **kwargs):
        #print "SynapseEvent %r" % kwargs
        super(SynapseEvent, self).__init__(is_state=is_state, **kwargs)


class SynapseStateEvent(SynapseEvent):
    required_keys = SynapseEvent.required_keys + [
        "is_state",
        "state_key",
    ]

    TEMPLATE = SynapseEventStateTemplate

    def __init__(self, **kwargs):
        kwargs["is_state"] = True
        super(SynapseStateEvent, self).__init__(**kwargs)
