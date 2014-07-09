# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.util.dbutils import DbPool
from events import PostEventMixin, BaseEvent, InvalidHttpRequestError

from sqlite3 import IntegrityError

import synapse.util.stringutils as stringutils

import base64
import json
import re
import time
import urllib


class RegisterEvent(PostEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
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
            pass

        if desired_user_id:
            try:
                (user_id, token) = yield DbPool.get().runInteraction(
                                       self._register, desired_user_id)
            except InvalidHttpRequestError as e:
                defer.returnValue((e.get_status_code(), e.get_response_body()))

            defer.returnValue((200,
                              {"user_id": user_id, "access_token": token}))
        else:
            # autogen a random user ID
            (user_id, token) = (None, None)
            attempts = 0
            while not user_id and not token:
                try:
                    (user_id, token) = yield DbPool.get().runInteraction(
                                            self._register,
                                            self._generate_user_id())
                except InvalidHttpRequestError:
                    # if user id is taken, just generate another
                    attempts += 1
                    if attempts > 5:
                        defer.returnValue((500, "Cannot generate user ID."))

            defer.returnValue((200,
                              {"user_id": user_id, "access_token": token}))

    # TODO this should probably be shifted out to another module
    def _register(self, txn, user_id):
        now = int(time.time())

        try:
            txn.execute("INSERT INTO users(name, creation_ts) VALUES (?,?)",
                        [user_id, now])
        except IntegrityError:
            raise InvalidHttpRequestError(400, "User ID already taken.")

        # urlsafe variant uses _ and - so use . as the separator
        token = (base64.urlsafe_b64encode(user_id) + "." +
                 stringutils.random_string(18))

        # it's possible for this to get a conflict, but only for a single user
        # since tokens are namespaced based on their user ID
        txn.execute("INSERT INTO access_tokens(user_id, token) " +
                    "VALUES (?,?)", [txn.lastrowid, token])

        return (user_id, token)

    def _generate_user_id(self):
        return "-" + stringutils.random_string(18)