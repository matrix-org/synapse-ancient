# -*- coding: utf-8 -*-
"""This module contains classes for streaming from the event stream: /events."""
from twisted.internet import defer

from synapse.api.errors import EventStreamError
from synapse.api.events.room import RoomMemberEvent, MessageEvent
from synapse.api.streams import FilterStream, StreamData


class MessagesStreamData(StreamData):
    EVENT_TYPE = MessageEvent.TYPE

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_key, to_key):
        (data, latest_ver) = yield self.store.get_message_stream(
                                user_id=user_id,
                                from_key=from_key,
                                to_key=to_key
                                )
        defer.returnValue((data, latest_ver))


class RoomMemberStreamData(StreamData):
    EVENT_TYPE = RoomMemberEvent.TYPE

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_key, to_key):
        (data, latest_ver) = yield self.store.get_room_member_stream(
                                user_id=user_id,
                                from_key=from_key,
                                to_key=to_key
                                )

        defer.returnValue((data, latest_ver))


class EventStream(FilterStream):

    SEPARATOR = '_'

    def __init__(self, user_id, stream_data_list):
        super(EventStream, self).__init__()
        self.user_id = user_id
        self.stream_data = stream_data_list

    @defer.inlineCallbacks
    def get_chunk(self, from_tok=None, to_tok=None, direction=None, limit=None):
        # no support for limit and dir=b, makes no sense on the EventStream
        if limit or direction != 'f':
            raise EventStreamError(400, "Limit and dir=b not supported.")

        if from_tok == FilterStream.TOK_START:
            from_tok = EventStream.SEPARATOR.join(
                           ["0"] * len(self.stream_data))

        if to_tok == FilterStream.TOK_END:
            to_tok = EventStream.SEPARATOR.join(
                           ["-1"] * len(self.stream_data))

        try:
            (chunk_data, next_tok) = yield self._get_chunk_data(from_tok,
                                                                to_tok)

            defer.returnValue({
                "chunk": chunk_data,
                "start": from_tok,
                "end": next_tok
            })
        except EventStreamError as e:
            print e
            raise EventStreamError(400, "Bad tokens supplied.")

    @defer.inlineCallbacks
    def _get_chunk_data(self, from_tok, to_tok):
        """ Get event data between the two tokens.

        Tokens are SEPARATOR separated values representing pkey values of
        certain tables, and the position determines the StreamData invoked
        according to the STREAM_DATA list.

        The magic value '-1' can be used to get the latest value.

        Args:
            from_tok - The token to start from.
            to_tok - The token to end at. Must have values > from_tok or be -1.
        Returns:
            A list of event data.
        Raises:
            EventStreamError if something went wrong.
        """
        # sanity check
        if (from_tok.count(EventStream.SEPARATOR) !=
                to_tok.count(EventStream.SEPARATOR) or
                (from_tok.count(EventStream.SEPARATOR) + 1) !=
                len(self.stream_data)):
            raise EventStreamError("Token lengths don't match.")

        chunk = []
        next_ver = []
        for i, (from_pkey, to_pkey) in enumerate(zip(
                                        from_tok.split(EventStream.SEPARATOR),
                                        to_tok.split(EventStream.SEPARATOR))):
            # convert to ints and sanity check
            try:
                ifrom = int(from_pkey)
                ito = int(to_pkey)
                if ifrom < 0 or ifrom > ito and ito != -1:
                    raise EventStreamError("Bad index.")
            except ValueError:
                raise EventStreamError("Index not integer.")

            (event_chunk, max_pkey) = yield self.stream_data[i].get_rows(
                                        self.user_id, ifrom, ito)

            chunk += event_chunk
            next_ver.append(str(max_pkey))

        defer.returnValue((chunk, EventStream.SEPARATOR.join(next_ver)))
