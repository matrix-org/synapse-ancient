# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.util.dbutils import DbPool
from events import PostEventMixin, BaseEvent

from sqlite3 import IntegrityError

import synapse.util.stringutils as stringutils

import json
import re
import time


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
        except ValueError:
            defer.returnValue((400, "No JSON object."))
        except KeyError:
            pass

        if desired_user_id:
            (user_id, token) = yield DbPool.get().runInteraction(self._register,
                                                                desired_user_id)
            if user_id and token:
                defer.returnValue((200,
                                  {"user_id": user_id, "access_token": token}))
            else:
                defer.returnValue((400,
                                  "User ID already taken."))
        else:
            defer.returnValue((500, "Uh oh"))

    # TODO this should probably be shifted out to another module
    def _register(self, txn, user_id):
        now = int(time.time())
        token = stringutils.random_string(24)
        device_id = "NO_DEVICE_ID"

        try:
            txn.execute("INSERT INTO users(name, creation_ts) VALUES (?,?)",
                        [user_id, now])
        except IntegrityError:
            return (None, None)

        txn.execute("INSERT INTO access_tokens(user_id, device_id, token) " +
                    "VALUES (?,?,?)", [txn.lastrowid, device_id, token])

        return (user_id, token)

    # TODO how to autogen a non-conflicting userid
    def _generate_user_id(self):
        return "fluffle"