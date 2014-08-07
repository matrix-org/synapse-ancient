# -*- coding: utf-8 -*-
"""This module contains REST servlets to do with event streaming, /events."""
from twisted.internet import defer

from synapse.api.errors import SynapseError
from synapse.api.streams import PaginationConfig
from synapse.rest.base import RestServlet, client_path_pattern


class EventStreamRestServlet(RestServlet):
    PATTERN = client_path_pattern("/events$")

    DEFAULT_LONGPOLL_TIME_MS = 5000

    @defer.inlineCallbacks
    def on_GET(self, request):
        auth_user = yield self.auth.get_user_by_req(request)

        handler = self.handlers.event_stream_handler
        pagin_config = PaginationConfig.from_request(request)
        timeout = EventStreamRestServlet.DEFAULT_LONGPOLL_TIME_MS
        if "timeout" in request.args:
            try:
                timeout = int(request.args["timeout"][0])
            except ValueError:
                raise SynapseError(400, "timeout must be in milliseconds.")

        chunk = yield handler.get_stream(auth_user.to_string(), pagin_config,
                                         timeout=timeout)
        defer.returnValue((200, chunk))

    def on_OPTIONS(self, request):
        return (200, {})


def register_servlets(hs, http_server):
    EventStreamRestServlet(hs).register(http_server)
