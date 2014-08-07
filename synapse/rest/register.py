# -*- coding: utf-8 -*-
"""This module contains REST servlets to do with registration: /register"""
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError, client_path_pattern

import json
import urllib


class RegisterRestServlet(RestServlet):
    PATTERN = client_path_pattern("/register$")

    @defer.inlineCallbacks
    def on_POST(self, request):
        desired_user_id = None
        try:
            register_json = json.loads(request.content.read())
            if type(register_json["user_id"]) == unicode:
                desired_user_id = register_json["user_id"]
                if urllib.quote(desired_user_id) != desired_user_id:
                    raise InvalidHttpRequestError(
                        400,
                        "User ID must only contain characters which do not " +
                        "require URL encoding.")
        except ValueError:
            defer.returnValue((400, "No JSON object."))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        except KeyError:
            pass  # user_id is optional

        handler = self.handlers.registration_handler
        (user_id, token) = yield handler.register(localpart=desired_user_id)
        defer.returnValue((200,
                           {"user_id": user_id, "access_token": token}))

    def on_OPTIONS(self, request):
        return (200, {})


def register_servlets(hs, http_server):
    RegisterRestServlet(hs).register(http_server)
