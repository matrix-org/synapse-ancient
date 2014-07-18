# -*- coding: utf-8 -*-
from . import SynapseEvent, SynapseStateEvent
from .validator import RoomTopicTempalate, RoomMemberTemplate, MessageTemplate


class RoomTopicEvent(SynapseStateEvent):
    TYPE = "sy.room.topic"

    TEMPLATE = RoomTopicTempalate

    def __init__(self, **kwargs):
        kwargs["type"] = RoomTopicEvent.TYPE
        kwargs["state_key"] = None
        super(RoomTopicEvent, self).__init__(**kwargs)

    def __getattr__(self, key):
        if key == "topic":
            return self.content.topic
        else:
            return super(RoomTopicEvent, self).__getattr__(key)


class RoomMemberEvent(SynapseStateEvent):
    TYPE = "sy.room.member"

    TEMPLATE = RoomMemberTemplate

    def __init__(self, target_user, **kwargs):
        kwargs["type"] = RoomMemberEvent.TYPE
        kwargs["state_key"] = target_user

        super(RoomMemberEvent, self).__init__(**kwargs)

    def __getattr__(self, key):
        if key == "target_user":
            return self.state_key
        elif key == "membership":
            return self.content["membership"]
        else:
            return super(RoomMemberEvent, self).__getattr__(key)


class MessageEvent(SynapseEvent):
    TYPE = "sy.room.message"

    TEMPLATE = MessageTemplate

    required_keys = SynapseEvent.required_keys + ["msg_id"]

    def __init__(self, **kwargs):
        kwargs["type"] = MessageEvent.TYPE
        super(MessageEvent, self).__init__(**kwargs)
