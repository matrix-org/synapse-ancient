# -*- coding: utf-8 -*-
"""This module contains events to do with registration: /register"""
from twisted.internet import defer

from synapse.api.events.register import RegistrationEvent, RegistrationError
from synapse.util.dbutils import DbPool
from base import PostEventMixin, RestEvent, InvalidHttpRequestError

import json
import re
import urllib


class RegisterRestEvent(PostEventMixin, RestEvent):

    def get_pattern(self):
        return re.compile("^/register$")

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

        event = RegistrationEvent(db_pool=DbPool.get(), user_id=desired_user_id)
        try:
            (user_id, token) = yield event.register()
            defer.returnValue((200,
                               {"user_id": user_id, "access_token": token}))
        except RegistrationError as e:
            defer.returnValue((e.code, e.msg))

