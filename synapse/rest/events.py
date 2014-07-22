# -*- coding: utf-8 -*-
"""This module contains REST servlets to do with event streaming, /events."""
from twisted.internet import defer

from synapse.api.errors import SynapseError
from synapse.api.streams.base import FilterStream
from synapse.rest.base import RestServlet, InvalidHttpRequestError

import re


class EventStreamRestServlet(RestServlet):

    def register(self, http_server):
        pattern = re.compile("^/events$")
        http_server.register_path("GET", pattern, self.on_GET)
        http_server.register_path("OPTIONS", pattern, self.on_OPTIONS)

    @defer.inlineCallbacks
    def on_GET(self, request):
        try:
            auth_user_id = yield (self.auth.get_user_by_req(request))

            handler = self.handler_factory.event_stream_handler()
            params = self._get_stream_parameters(request)
            chunk = yield handler.get_stream(auth_user_id, **params)
            defer.returnValue((200, chunk))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))

        defer.returnValue((500, "This is not the stream you are looking for."))

    def _get_stream_parameters(self, request):
        params = {
            "from_tok": FilterStream.TOK_START,
            "to_tok": FilterStream.TOK_END,
            "limit": None,
            "direction": 'f',
            "timeout": 5
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

    def on_OPTIONS(self, request):
        return (200, {})
