# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.streams import PaginationConfig
from base import RestServlet, client_path_pattern


class ImSyncRestServlet(RestServlet):
    PATTERN = client_path_pattern("/im/sync$")

    @defer.inlineCallbacks
    def on_GET(self, request):
        user = yield self.auth.get_user_by_req(request)
        with_feedback = "feedback" in request.args
        pagination_config = PaginationConfig.from_request(request)
        handler = self.handlers.message_handler
        content = yield handler.snapshot_all_rooms(
            user_id=user.to_string(),
            pagin_config=pagination_config,
            feedback=with_feedback)

        defer.returnValue((200, content))


def register_servlets(hs, http_server):
    ImSyncRestServlet(hs).register(http_server)
