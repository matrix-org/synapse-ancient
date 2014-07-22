# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with profile: /profile/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError

import re


class ProfileDisplaynameRestServlet(RestServlet):
    def register(self, http_server):
        http_server.register_path("GET",
                re.compile("^/profile/(?P<user_id>[^/]*)/displayname"),
                self.on_GET)

    def on_GET(self, request, user_id):
        return defer.returnValue((200, "Frank"))


def register_servlets(hs, http_server):
    ProfileDisplaynameRestServlet(hs).register(http_server)
