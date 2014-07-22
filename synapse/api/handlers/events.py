# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.handlers import BaseHandler
from synapse.api.streams.event import (EventStream, MessagesStreamData,
                                       RoomMemberStreamData)


class EventStreamHandler(BaseHandler):

    @defer.inlineCallbacks
    def get_stream(self, auth_user_id, timeout=0, from_tok=None, to_tok=None,
                   direction=None, limit=None):
        try:
            # register interest in receiving new events
            self.notifier.store_events_for(user_id=auth_user_id,
                                           from_tok=from_tok)

            # check for previous events
            event_stream = EventStream(auth_user_id,
                              [
                                  MessagesStreamData(self.store),
                                  RoomMemberStreamData(self.store)
                              ])
            data_chunk = yield event_stream.get_chunk(
                            from_tok=from_tok,
                            to_tok=to_tok,
                            direction=direction,
                            limit=limit
                        )

            # if there are previous events, return those. If not, wait on the
            # new events for 'timeout' seconds.
            if len(data_chunk["chunk"]) == 0 and timeout != 0:
                results = yield self.notifier.get_events_for(
                                user_id=auth_user_id,
                                timeout=timeout)
                if results:
                    defer.returnValue(results)

            defer.returnValue(data_chunk)
        finally:
            # cleanup
            self.notifier.purge_events_for(user_id=auth_user_id)