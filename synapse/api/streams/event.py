# -*- coding: utf-8 -*-
"""This module contains classes for streaming from the event stream: /events."""
from twisted.internet import defer

from synapse.util.dbutils import DbPool
from synapse.rest.room import MessageEvent, RoomMemberEvent
from synapse.rest.base import InvalidHttpRequestError  # TODO remove
from base import FilterStream, StreamData


class MessagesStreamData(StreamData):

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_pkey, to_pkey):
        (rows, pkey) = yield DbPool.get().runInteraction(self._get_rows,
                                                    user_id, from_pkey, to_pkey)
        defer.returnValue((rows, pkey))

    def _get_rows(self, txn, user_id, from_pkey, to_pkey):
        # work out which rooms this user is joined in on and join them with
        # the room id on the messages table, bounded by the specified pkeys

        # get all messages where the *current* membership state is 'join' for
        # this user in that room.
        query = ("SELECT messages.* FROM messages WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = messages.room_id ORDER BY id DESC LIMIT 1) " +
            "AND messages.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND messages.id < ?"
            query_args.append(to_pkey)

        txn.execute(query, query_args)

        col_headers = [i[0] for i in txn.description]
        result_set = txn.fetchall()
        data = []
        last_pkey = from_pkey
        for result in result_set:
            event = MessageEvent()
            result_dict = dict(zip(col_headers, result))
            last_pkey = result_dict["id"]
            event_data = event.get_event_data(result_dict)
            data.append(event_data)

        return (data, last_pkey)


class RoomMemberStreamData(StreamData):

    @defer.inlineCallbacks
    def get_rows(self, user_id, from_pkey, to_pkey):
        (rows, pkey) = yield DbPool.get().runInteraction(self._get_rows,
                                                    user_id, from_pkey, to_pkey)
        defer.returnValue((rows, pkey))

    def _get_rows(self, txn, user_id, from_pkey, to_pkey):
        # get all room membership events for rooms which the user is *currently*
        # joined in on.
        query = ("SELECT rm.* FROM room_memberships rm WHERE ? IN " +
            "(SELECT membership from room_memberships WHERE user_id=? AND " +
            "room_id = rm.room_id ORDER BY id DESC LIMIT 1) " +
            "AND rm.id > ?")
        query_args = ["join", user_id, from_pkey]

        if to_pkey != -1:
            query += " AND rm.id < ?"
            query_args.append(to_pkey)

        txn.execute(query, query_args)

        col_headers = [i[0] for i in txn.description]
        result_set = txn.fetchall()
        data = []
        last_pkey = from_pkey
        for result in result_set:
            event = RoomMemberEvent()
            result_dict = dict(zip(col_headers, result))
            last_pkey = result_dict["id"]
            event_data = event.get_event_data(result_dict)
            data.append(event_data)

        return (data, last_pkey)


class EventStream(FilterStream):

    # order here maps onto tokens
    STREAM_DATA = [MessagesStreamData(),
                   RoomMemberStreamData()]

    SEPARATOR = '_'

    def __init__(self, user_id):
        super(EventStream, self).__init__()
        self.user_id = user_id

    @defer.inlineCallbacks
    def get_chunk(self, from_tok=None, to_tok=None, direction=None, limit=None):
        # TODO add support for limit and dir=b
        if limit or direction != 'f':
            raise InvalidHttpRequestError(400, "Limit and dir=b not supported.")

        if from_tok == FilterStream.TOK_START:
            from_tok = EventStream.SEPARATOR.join(
                           ["0"] * len(EventStream.STREAM_DATA))

        if to_tok == FilterStream.TOK_END:
            to_tok = EventStream.SEPARATOR.join(
                           ["-1"] * len(EventStream.STREAM_DATA))

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
            raise InvalidHttpRequestError(400, "Bad tokens supplied.")

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
                len(EventStream.STREAM_DATA)):
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

            (event_chunk, max_pkey) = yield EventStream.STREAM_DATA[i].get_rows(
                                        self.user_id, ifrom, ito)

            chunk += event_chunk
            next_ver.append(str(max_pkey))

        defer.returnValue((chunk, EventStream.SEPARATOR.join(next_ver)))


class EventStreamError(Exception):
    pass
