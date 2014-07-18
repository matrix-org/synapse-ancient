# -*- coding: utf-8 -*-
from . import SynapseEvent


class RoomTopicEvent(SynapseEvent):
    TYPE = "sy.room.topic"

    valid_keys = [
        "type",
        "content",
        "room_id",
        "auth_user_id"
    ]

    def __init__(self, **kwargs):
        super(RoomTopicEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"topic": u"string"}


class RoomMemberEvent(SynapseEvent):
    TYPE = "sy.room.member"

    valid_keys = [
        "type",
        "room_id",
        "auth_user_id",  # initiator
        "user_id",  # target
        "membership",  # action
        "content"
    ]

    def __init__(self, **kwargs):
        super(RoomMemberEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"membership": u"string"}


class MessageEvent(SynapseEvent):
    TYPE = "sy.room.message"

    valid_keys = [
        "type",
        "room_id",
        "user_id",
        "msg_id",
        "auth_user_id",
        "content"
    ]

    def __init__(self, **kwargs):
        super(MessageEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"msgtype": u"string"}