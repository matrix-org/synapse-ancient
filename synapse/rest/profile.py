# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with profile: /profile/<paths> """
from twisted.internet import defer

from synapse.api.errors import SynapseError, cs_error

from base import RestServlet, InvalidHttpRequestError

import json
import re


class ProfileDisplaynameRestServlet(RestServlet):
    PATTERN = re.compile("^/profile/(?P<user_id>[^/]*)/displayname")

    @defer.inlineCallbacks
    def on_GET(self, request, user_id):
        user = self.hs.parse_userid(user_id)

        displayname = yield self.handlers.profile_handler.get_displayname(user)

        defer.returnValue((200, displayname))

    @defer.inlineCallbacks
    def on_PUT(self, request, user_id):
        user = self.hs.parse_userid(user_id)

        try:
            new_name = json.loads(request.content.read())
        except:
            defer.returnValue((400, "Unable to parse name"))

        try:
            auth_user_id = yield self.auth.get_user_by_req(request)
            yield self.handlers.profile_handler.set_displayname(user,
                    auth_user_id, new_name)
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

        defer.returnValue((200, ""))


def register_servlets(hs, http_server):
    ProfileDisplaynameRestServlet(hs).register(http_server)
