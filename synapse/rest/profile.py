# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with profile: /profile/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError

import re


class ProfileDisplaynameRestServlet(RestServlet):

    def __init__(self, hs):
        super(ProfileDisplaynameRestServlet, self).__init__(hs)

        self.datastore = hs.get_datastore()

    def register(self, http_server):
        http_server.register_path("GET",
                re.compile("^/profile/(?P<user_id>[^/]*)/displayname"),
                self.on_GET)

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


def register_servlets(hs, http_server):
    ProfileDisplaynameRestServlet(hs).register(http_server)
