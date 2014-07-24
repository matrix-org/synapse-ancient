# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with profile: /profile/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError

import json
import re


class ProfileDisplaynameRestServlet(RestServlet):
    PATTERN = re.compile("^/profile/(?P<user_id>[^/]*)/displayname")

    def __init__(self, hs):
        super(ProfileDisplaynameRestServlet, self).__init__(hs)

        self.datastore = hs.get_datastore()

    @defer.inlineCallbacks
    def on_GET(self, request, user_id):
        user = self.hs.parse_userid(user_id)

        if user.is_mine:
            displayname = yield self.datastore.get_profile_displayname(
                    user.localpart)

            defer.returnValue((200, displayname))
        else:
            # TODO(paul): This should use the server-server API to ask another
            # HS
            defer.returnValue((200, "Bob"))

    @defer.inlineCallbacks
    def on_PUT(self, request, user_id):
        user = self.hs.parse_userid(user_id)

        if not user.is_mine:
            defer.returnValue((400, "User is not hosted on this Home Server"))

        try:
            auth_user_id = yield self.auth.get_user_by_req(request)
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

        if user.localpart != auth_user_id:
            defer.returnValue((400, "Cannot set another user's displayname"))

        try:
            new_name = json.loads(request.content.read())
        except:
            defer.returnValue((400, "Unable to parse name"))

        yield self.datastore.set_profile_displayname(user.localpart, new_name)
        defer.returnValue((200, ""))


def register_servlets(hs, http_server):
    ProfileDisplaynameRestServlet(hs).register(http_server)
