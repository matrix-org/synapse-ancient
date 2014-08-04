# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError
from synapse.api.streams import PaginationConfig
from base import RestServlet

import re


class UserRoomListRestServlet(RestServlet):
    # TODO(markjh): Namespace the client URI paths
    PATTERN = re.compile("^/users/(?P<sender_id>[^/]*)/rooms/list$")

    @defer.inlineCallbacks
    def on_GET(self, request, sender_id):
        user = yield self.auth.get_user_by_req(request)
        if user.to_string() != sender_id:
            raise SynapseError(403, "Cannot see room list of other users.")
        with_feedback = "feedback" in request.args
        pagination_config = PaginationConfig.from_request(request)
        handler = self.handlers.message_handler
        content = yield handler.snapshot_all_rooms(
            user_id=user.to_string(),
            pagin_config=pagination_config,
            feedback=with_feedback)

        defer.returnValue((200, content))


def register_servlets(hs, http_server):
    UserRoomListRestServlet(hs).register(http_server)
