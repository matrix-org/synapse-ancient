# twisted imports
from twisted.enterprise import adbapi
from twisted.internet import defer

# trial imports
from twisted.trial import unittest

from synapse.api.auth import Auth
from synapse.api.events.room import MessageEvent, RoomMemberEvent
from synapse.persistence import read_schema
from synapse.util.dbutils import DbPool

# python imports
import json
import os
import sqlite3

from ..utils import MockHttpServer


class MessageTestCase(unittest.TestCase):
    """ Checks that messages can be PUT/GET. """

    def _setup_db(self, db_name):
        # FIXME: This is basically a copy of synapse.app.homeserver's setup
        # routine. It would be nice if we could reuse that.
        dbpool = adbapi.ConnectionPool(
            'sqlite3', db_name, check_same_thread=False,
            cp_min=1, cp_max=1)

        schemas = [
            "im"
        ]

        DbPool.set(dbpool)

        for sql_loc in schemas:
            sql_script = read_schema(sql_loc)

            with sqlite3.connect(db_name) as db_conn:
                c = db_conn.cursor()
                c.executescript(sql_script)
                c.close()
                db_conn.commit()

    def setUp(self):
        self._setup_db("_temp.db")
        self.mock_server = MockHttpServer()
        self.mock_data_store = None  # TODO
        Auth.mod_registered_user = MockRegisteredUserModule("sid1")
        MessageEvent().register(self.mock_server, self.mock_data_store)
        RoomMemberEvent().register(self.mock_server, self.mock_data_store)

    def tearDown(self):
        try:
            os.remove("_temp.db")
        except:
            pass

    @defer.inlineCallbacks
    def _test_invalid_puts(self, path):
        # missing keys or invalid json
        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{}')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{"_name":"bob"}')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{"nao')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '[{"_name":"bob"},{"_name":"jill"}]')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, 'text only')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '')
        self.assertEquals(400, code)

    @defer.inlineCallbacks
    def test_room_members(self):
        path = "/rooms/rid1/members/sid1/state"
        self._test_invalid_puts(path)

        # valid keys, wrong types
        (code, response) = yield self.mock_server.trigger("PUT", path,
                           '{"membership":["join","leave","invite"]}')
        self.assertEquals(400, code)

        # valid join message
        (code, response) = yield self.mock_server.trigger("PUT", path,
                           '{"membership":"join"}')
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads('{"membership":"join"}'), response)

    @defer.inlineCallbacks
    def test_messages_in_room(self):
        path = "/rooms/rid1/messages/sid1/mid1"
        self._test_invalid_puts(path)

        (code, response) = yield self.mock_server.trigger("PUT", path,
                           '{"body":"test","msgtype":{"type":"a"}}')
        self.assertEquals(400, code)

        # custom message types
        (code, response) = yield self.mock_server.trigger("PUT", path,
                           '{"body":"test","msgtype":"test.custom.text"}')
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads('{"body":"test","msgtype":' +
                          '"test.custom.text"}'), response)

        # sy.text message type
        path = "/rooms/rid1/messages/sid1/mid2"
        (code, response) = yield self.mock_server.trigger("PUT", path,
                           '{"body":"test2","msgtype":"sy.text"}')
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads('{"body":"test2","msgtype":' +
                          '"sy.text"}'), response)


class MockRegisteredUserModule():

    def __init__(self, user_id):
        self.user_id = user_id

    def get_user_by_req(self, request):
        return self.user_id

    def get_user_by_token(self, token):
        return self.user_id
