# -*- coding: utf-8 -*-
from . import SynapseEvent


class RoomTopicEvent(SynapseEvent):

    def get_template(self):
        return {"topic": u"string"}


class MessageEvent(SynapseEvent):

    def get_template(self):
        return {"msgtype": u"string"}