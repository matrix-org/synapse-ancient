# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.handlers import BaseHandler
from synapse.api.streams.event import (EventStream, MessagesStreamData,
                                       RoomMemberStreamData)


class EventStreamHandler(BaseHandler):

    stream_data_classes = [
        MessagesStreamData,
        RoomMemberStreamData
    ]

    def get_event_stream_token(self, event, store_id, start_token):
        """Return the next token after this event.

        Args:
            event (SynapseEvent): The incoming event
            store_id (int): The new storage ID assigned from the data store.
            start_token (str): The token the user started with.
        Returns:
            str: The end token.
        """
        for i, stream_cls in enumerate(EventStreamHandler.stream_data_classes):
            if stream_cls.EVENT_TYPE == event.type:
                # this is the stream for this event, so replace this part of
                # the token
                store_ids = start_token.split(EventStream.SEPARATOR)
                store_ids[i] = str(store_id)
                return EventStream.SEPARATOR.join(store_ids)
        raise RuntimeError("Didn't find a stream for this event %s" % event)

    @defer.inlineCallbacks
    def get_stream(self, auth_user_id, timeout=0, from_tok=None, to_tok=None,
                   direction=None, limit=None):
        """Gets events as an event stream for this user.

        This function looks for interesting *events* for this user. This is
        different from the notifier, which looks for interested *users* who may
        want to know about a single event.
        """
        try:
            # register interest in receiving new events
            self.notifier.store_events_for(user_id=auth_user_id,
                                           from_tok=from_tok)

            # construct an event stream with the correct data ordering
            stream_data_list = []
            for stream_class in EventStreamHandler.stream_data_classes:
                stream_data_list.append(stream_class(self.store))

            event_stream = EventStream(auth_user_id, stream_data_list)
            data_chunk = yield event_stream.get_chunk(
                            from_tok=from_tok,
                            to_tok=to_tok,
                            direction=direction,
                            limit=limit
                        )

            # if there are previous events, return those. If not, wait on the
            # new events for 'timeout' seconds.
            if len(data_chunk["chunk"]) == 0 and timeout != 0:
                results = yield defer.maybeDeferred(
                                    self.notifier.get_events_for,
                                    user_id=auth_user_id,
                                    timeout=timeout
                                )
                if results:
                    defer.returnValue(results)

            defer.returnValue(data_chunk)
        finally:
            # cleanup
            self.notifier.purge_events_for(user_id=auth_user_id)