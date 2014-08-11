# -*- coding: utf-8 -*-
from twisted.internet import defer

from base import RestServlet, client_path_pattern


class LoginRestServlet(RestServlet):
    PATTERN = client_path_pattern("/login$")

    def on_GET(self, request):
        return (200, {"type": "m.login.password"})


def register_servlets(hs, http_server):
    LoginRestServlet(hs).register(http_server)