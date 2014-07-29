# -*- coding: utf-8 -*-
from twisted.internet import defer

from base import RestServlet

import re


class UserRoomListRestServlet(RestServlet):
    PATTERN = re.compile("^/users/(?P<sender_id>[^/]*)/rooms/list$")

    @defer.inlineCallbacks
    def on_GET(self, request, sender_id):
        user = yield self.auth.get_user_by_req(request)
        handler = self.handlers.room_member_handler
        #content = yield handler.get_messages(
        #    room_id=room_id,
        #    user_id=user.to_string(),
        #    pagin_config=pagination_config,
        #    feedback=with_feedback)

        defer.returnValue((200, "NOT_IMPLEMENTED"))


def register_servlets(hs, http_server):
    UserRoomListRestServlet(hs).register(http_server)