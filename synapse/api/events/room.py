# -*- coding: utf-8 -*-
from . import SynapseEvent


class RoomTopicEvent(SynapseEvent):
    TYPE = "sy.room.topic"

    def __init__(self, content=None, pdu=None, **kwargs):
        super(RoomTopicEvent, self).__init__(content)
        self.type = RoomTopicEvent.TYPE

        if not pdu:
            self.room_id = kwargs["room_id"]
            self.auth_user_id = kwargs["auth_user_id"]
        else:
            pass  # TODO pdu impl

    def get_content_template(self):
        return {"topic": u"string"}


class RoomMemberEvent(SynapseEvent):
    TYPE = "sy.room.member"

    def __init__(self, content=None, pdu=None, **kwargs):
        super(RoomMemberEvent, self).__init__(content)
        self.type = RoomMemberEvent.TYPE

        if not pdu:
            self.room_id = kwargs["room_id"]
            self.auth_user_id = kwargs["auth_user_id"]  # initiator
            self.user_id = kwargs["user_id"]  # target
            self.membership = kwargs["membership"]  # action
        else:
            pass  # TODO pdu impl

    def get_content_template(self):
        return {"membership": u"string"}


class MessageEvent(SynapseEvent):
    TYPE = "sy.room.message"

    def __init__(self, content=None, pdu=None, **kwargs):
        super(MessageEvent, self).__init__(content)
        self.type = MessageEvent.TYPE

        if not pdu:
            self.room_id = kwargs["room_id"]
            self.user_id = kwargs["user_id"]
            self.msg_id = kwargs["msg_id"]
            self.auth_user_id = kwargs["auth_user_id"]
        else:
            pass  # TODO pdu impl

    def get_content_template(self):
        return {"msgtype": u"string"}