# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with profile: /profile/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError

import json
import re


class ProfileDisplaynameRestServlet(RestServlet):

    def __init__(self, hs):
        super(ProfileDisplaynameRestServlet, self).__init__(hs)

        self.datastore = hs.get_datastore()

    # TODO(paul): SUUURELY this can be done automatically at a lower level??
    def register(self, http_server):
        pattern = re.compile("^/profile/(?P<user_id>[^/]*)/displayname")

        http_server.register_path("GET", pattern, self.on_GET)
        http_server.register_path("PUT", pattern, self.on_PUT)

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

        ## TODO: Authentication

        try:
            new_name = json.loads(request.content.read())
        except:
            defer.returnValue((400, "Unable to parse name"))

        yield self.datastore.set_profile_displayname(user.localpart, new_name)
        defer.returnValue((200, ""))


def register_servlets(hs, http_server):
    ProfileDisplaynameRestServlet(hs).register(http_server)
