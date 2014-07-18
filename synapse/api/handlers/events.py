# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.handlers import BaseHandler
from synapse.api.streams.event import (EventStream, MessagesStreamData,
                                       RoomMemberStreamData)


class EventStreamHandler(BaseHandler):

    @defer.inlineCallbacks
    def get_stream(self, auth_user_id, **params):
        event_stream = EventStream(auth_user_id,
                          [
                              MessagesStreamData(self.store),
                              RoomMemberStreamData(self.store)
                          ])
        chunk = yield event_stream.get_chunk(**params)
        defer.returnValue(chunk)