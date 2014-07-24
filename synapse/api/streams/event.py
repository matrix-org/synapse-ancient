# -*- coding: utf-8 -*-
"""This module contains classes for streaming from the event stream: /events."""
from twisted.internet import defer

from synapse.api.errors import EventStreamError
from synapse.api.events.room import RoomMemberEvent, MessageEvent
from synapse.api.streams import PaginationStream, StreamData

import logging

logger = logging.getLogger(__name__)


class MessagesStreamData(StreamData):
    EVENT_TYPE = MessageEvent.TYPE

    def __init__(self, store, room_id=None):
        super(MessagesStreamData, self).__init__(store)
        self.room_id = room_id

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_key, to_key, limit):
        (data, latest_ver) = yield self.store.get_message_stream(
                                user_id=user_id,
                                from_key=from_key,
                                to_key=to_key,
                                limit=limit,
                                room_id=self.room_id
                                )
        defer.returnValue((data, latest_ver))


class RoomMemberStreamData(StreamData):
    EVENT_TYPE = RoomMemberEvent.TYPE

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_key, to_key, limit):
        (data, latest_ver) = yield self.store.get_room_member_stream(
                                user_id=user_id,
                                from_key=from_key,
                                to_key=to_key
                                )

        defer.returnValue((data, latest_ver))


class EventStream(PaginationStream):

    SEPARATOR = '_'

    def __init__(self, user_id, stream_data_list):
        super(EventStream, self).__init__()
        self.user_id = user_id
        self.stream_data = stream_data_list

    @defer.inlineCallbacks
    def get_chunk(self, config=None):
        # no support for limit on >1 streams, makes no sense.
        if config.limit and len(self.stream_data) > 1:
            raise EventStreamError(400,
                                  "Limit not supported on multiplexed streams.")

        # replace TOK_START and TOK_END with 0_0_0 or -1_-1_-1 depending.
        replacements = [
            (PaginationStream.TOK_START, "0"),
            (PaginationStream.TOK_END, "-1")
        ]
        for token, key in replacements:
            if config.from_tok == token:
                config.from_tok = EventStream.SEPARATOR.join(
                                            [key] * len(self.stream_data))
            if config.to_tok == token:
                config.to_tok = EventStream.SEPARATOR.join(
                                            [key] * len(self.stream_data))

        try:
            (chunk_data, next_tok) = yield self._get_chunk_data(config.from_tok,
                                                                config.to_tok,
                                                                config.limit)

            defer.returnValue({
                "chunk": chunk_data,
                "start": config.from_tok,
                "end": next_tok
            })
        except Exception as e:
            logger.error("Failed to get chunk. Config %s. Exception: %s" %
                        (config.dict(), e))
            raise EventStreamError(400, "Bad tokens supplied.")

    @defer.inlineCallbacks
    def _get_chunk_data(self, from_tok, to_tok, limit):
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
            raise EventStreamError(400, "Token lengths don't match.")

        chunk = []
        next_ver = []
        for i, (from_pkey, to_pkey) in enumerate(zip(
                                        from_tok.split(EventStream.SEPARATOR),
                                        to_tok.split(EventStream.SEPARATOR))):
            # convert to ints and sanity check
            try:
                ifrom = int(from_pkey)
                ito = int(to_pkey)
                if ifrom < -1 or ito < -1:
                    raise EventStreamError(400, "Bad index.")
            except ValueError:
                raise EventStreamError(400, "Index not integer.")

            (event_chunk, max_pkey) = yield self.stream_data[i].get_rows(
                                        self.user_id, ifrom, ito, limit)

            chunk += event_chunk
            next_ver.append(str(max_pkey))

        defer.returnValue((chunk, EventStream.SEPARATOR.join(next_ver)))
