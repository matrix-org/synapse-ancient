# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError
from base import RestServlet, client_path_pattern

import json


class LoginRestServlet(RestServlet):
    PATTERN = client_path_pattern("/login$")
    PASS_TYPE = "m.login.password"

    def on_GET(self, request):
        return (200, {"type": LoginRestServlet.PASS_TYPE})

    @defer.inlineCallbacks
    def on_POST(self, request):
        login_submission = _parse_json(request)
        try:
            if login_submission["type"] == LoginRestServlet.PASS_TYPE:
                result = yield self.do_password_login(login_submission)
                defer.returnValue(result)
            else:
                raise SynapseError(400, "Bad login type.")
        except KeyError:
            raise SynapseError(400, "Missing JSON keys.")

    @defer.inlineCallbacks
    def do_password_login(self, login_submission):
        handler = self.handlers.login_handler
        token = yield handler.login(
            user=login_submission["user"],
            password=login_submission["password"])
        defer.returnValue((200, {"access_token": token}))


class LoginFallbackRestServlet(RestServlet):
    PATTERN = client_path_pattern("/login/fallback$")

    def on_GET(self, request):
        # TODO(kegan): This should be returning some HTML which is capable of
        # hitting LoginRestServlet
        return (200, "")


def _parse_json(request):
    try:
        content = json.loads(request.content.read())
        if type(content) != dict:
            raise SynapseError(400, "Content must be a JSON object.")
        return content
    except ValueError:
        raise SynapseError(400, "Content not JSON.")


def register_servlets(hs, http_server):
    LoginRestServlet(hs).register(http_server)