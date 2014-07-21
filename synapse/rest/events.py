# -*- coding: utf-8 -*-
"""This module contains REST events to do with event streaming, /events."""
from twisted.internet import defer

from synapse.api.streams.base import FilterStream
from synapse.api.auth import AuthDecorator
from synapse.rest.base import GetEventMixin, RestEvent, InvalidHttpRequestError

import re


class EventStreamRestEvent(GetEventMixin, RestEvent):

    def get_pattern(self):
        return re.compile("^/events$")

    @defer.inlineCallbacks
    def on_GET(self, request):
        try:
            auth_user_id = (self.auth.get_mod(AccessTokenModule.NAME).
                            get_user_by_req(request))

            handler = self.handler_factory.event_stream_handler()
            params = self._get_stream_parameters(request)
            chunk = yield handler.get_stream(auth_user_id, **params)
            defer.returnValue((200, chunk))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        defer.returnValue((500, "This is not the stream you are looking for."))

    def _get_stream_parameters(self, request):
        params = {
            "from_tok": FilterStream.TOK_START,
            "to_tok": FilterStream.TOK_END,
            "limit": None,
            "direction": 'f'
        }
        try:
            if request.args["dir"][0] not in ["f", "b"]:
                raise InvalidHttpRequestError(400, "Unknown dir value.")
            params["direction"] = request.args["dir"][0]
        except KeyError:
            pass  # dir is optional

        if "from" in request.args:
            params["from_tok"] = request.args["from"][0]
        if "to" in request.args:
            params["to_tok"] = request.args["to"][0]
        if "limit" in request.args:
            try:
                params["limit"] = request.args["limit"][0]
            except ValueError:
                raise InvalidHttpRequestError(400,
                    "limit cannot be used with this stream.")

        return params