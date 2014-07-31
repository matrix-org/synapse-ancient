# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with presence: /presence/<paths> """
from twisted.internet import defer

from base import RestServlet

import json
import re


class PresenceStatusRestServlet(RestServlet):
    PATTERN = re.compile("^/presence/(?P<user_id>[^/]*)/status")

    @defer.inlineCallbacks
    def on_GET(self, request, user_id):
        auth_user = yield self.auth.get_user_by_req(request)
        user = self.hs.parse_userid(user_id)

        state = yield self.handlers.presence_handler.get_state(
                target_user=user, auth_user=auth_user)

        defer.returnValue((200, state))

    @defer.inlineCallbacks
    def on_PUT(self, request, user_id):
        auth_user = yield self.auth.get_user_by_req(request)
        user = self.hs.parse_userid(user_id)

        state = {}
        try:
            content = json.loads(request.content.read())

            state["state"] = content.pop("state")

            if "status_msg" in content:
                state["status_msg"] = content.pop("status_msg")

            if content:
                raise KeyError()
        except:
            defer.returnValue((400, "Unable to parse state"))

        yield self.handlers.presence_handler.set_state(
                target_user=user, auth_user=auth_user, state=state)

        defer.returnValue((200, ""))


def register_servlets(hs, http_server):
    PresenceStatusRestServlet(hs).register(http_server)
