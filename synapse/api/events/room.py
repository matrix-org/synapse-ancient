# -*- coding: utf-8 -*-
from . import SynapseEvent


class RoomTopicEvent(SynapseEvent):
    TYPE = "sy.room.topic"

    def __init__(self, **kwargs):
        kwargs["state_key"] = ""
        super(RoomTopicEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"topic": u"string"}


class RoomMemberEvent(SynapseEvent):
    TYPE = "sy.room.member"

    valid_keys = SynapseEvent.valid_keys + [
        "target_user_id",  # target
        "membership",  # action
    ]

    def __init__(self, **kwargs):
        if "target_user_id" in kwargs:
            kwargs["state_key"] = kwargs["target_user_id"]
        super(RoomMemberEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"membership": u"string"}


class MessageEvent(SynapseEvent):
    TYPE = "sy.room.message"

    valid_keys = SynapseEvent.valid_keys + [
        "msg_id",  # unique per room + user combo
    ]

    def __init__(self, **kwargs):
        super(MessageEvent, self).__init__(**kwargs)

    def get_content_template(self):
        return {"msgtype": u"string"}