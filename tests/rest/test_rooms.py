# -*- coding: utf-8 -*-
"""Tests REST events for /rooms paths."""

# twisted imports
from twisted.enterprise import adbapi
from twisted.internet import defer

# trial imports
from twisted.trial import unittest

from synapse.api.auth import Auth
from synapse.api.events.room import (MessageEvent, RoomMemberEvent,
                                     RoomTopicEvent)
from synapse.api.event_store import EventStore
from synapse.persistence import read_schema
from synapse.util.dbutils import DbPool

# python imports
import json
import os
import sqlite3

from ..utils import MockHttpServer, MockRegisteredUserModule

DB_PATH = "_temp.db"


def _setup_db(db_name, schemas):
    # FIXME: This is basically a copy of synapse.app.homeserver's setup
    # routine. It would be nice if we could reuse that.
    dbpool = adbapi.ConnectionPool(
        'sqlite3', db_name, check_same_thread=False,
        cp_min=1, cp_max=1)

    DbPool.set(dbpool)

    for sql_loc in schemas:
        sql_script = read_schema(sql_loc)

        with sqlite3.connect(db_name) as db_conn:
            c = db_conn.cursor()
            c.executescript(sql_script)
            c.close()
            db_conn.commit()


class RoomsPermissionsTestCase(unittest.TestCase):
    """ Tests room permissions. """
    user_id = "sid1"

    def setUp(self):
        _setup_db(DB_PATH, ["im", "users"])

    def tearDown(self):
        try:
            os.remove(DB_PATH)
        except:
            pass

    def test_send_message(self):
        # send message in uncreated room

        # send message in created room not joined (no state)

        # send message in created room and invited

        # send message in created room and joined

        # send message in created room and left
        pass

    def test_topic_perms(self):
        # set topic in uncreated room

        # set topic in created room not joined (no state)

        # set topic in created room and invited

        # set topic in created room and joined

        # set topic in created room and left

        # get topic in uncreated room

        # get topic in PUBLIC room

        # get topic in PRIVATE room
        pass

    def test_membership_perms(self):
        # get membership of self, get membership of other, uncreated room

        # get membership of self, get membership of other, public room + invite

        # get membership of self, get membership of other, public room + joined

        # get membership of self, get membership of other, public room + left

        # get membership of self, get membership of other, private room + invite

        # get membership of self, get membership of other, private room + joined

        # get membership of self, get membership of other, private room + left

        # set membership of self, get membership of other, uncreated room

        # set membership of self, get membership of other, public room + invite

        # set membership of self, get membership of other, public room + joined

        # set membership of self, get membership of other, public room + left

        # set membership of self, get membership of other, private room + invite

        # set membership of self, get membership of other, private room + joined

        # set membership of self, get membership of other, private room + left
        pass


class RoomsCreateTestCase(unittest.TestCase):
    """ Tests room creation for /rooms. """
    user_id = "sid1"

    def setUp(self):
        _setup_db(DB_PATH, ["im", "users"])

    def tearDown(self):
        try:
            os.remove(DB_PATH)
        except:
            pass

    def test_post_room(self):
        # POST with no config keys

        # POST with visibility config key

        # POST with custom config keys

        # POST with custom + known config keys

        # POST with invalid content / paths
        pass

    def test_put_room(self):
        # PUT with no config keys

        # PUT with known config keys

        # PUT with custom config keys

        # PUT with custom + known config keys

        # PUT with invalid content / paths / room names

        # PUT with conflicting room ID
        pass


class RoomsTestCase(unittest.TestCase):
    """ Tests /rooms REST events. """
    user_id = "sid1"

    def setUp(self):
        _setup_db(DB_PATH, ["im"])
        self.mock_server = MockHttpServer()
        self.mock_data_store = EventStore()
        Auth.mod_registered_user = MockRegisteredUserModule(self.user_id)
        MessageEvent().register(self.mock_server, self.mock_data_store)
        RoomMemberEvent().register(self.mock_server, self.mock_data_store)
        RoomTopicEvent().register(self.mock_server, self.mock_data_store)

    def tearDown(self):
        try:
            os.remove(DB_PATH)
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
    def test_rooms_topic(self):
        path = "/rooms/rid1/topic"
        self._test_invalid_puts(path)

        # valid key, wrong type
        content = '{"topic":["Topic name"]}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code)

        # nothing should be there
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(404, code)

        # valid put
        content = '{"topic":"Topic name"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code)

        # valid get
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads(content), response)

        # valid put with extra keys
        content = '{"topic":"Seasons","subtopic":"Summer"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code)

        # valid get
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads(content), response)

    @defer.inlineCallbacks
    def test_rooms_members_state(self):
        path = "/rooms/rid1/members/%s/state" % self.user_id
        self._test_invalid_puts(path)

        # valid keys, wrong types
        content = '{"membership":["join","leave","invite"]}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code)

        # valid join message
        content = '{"membership":"join"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads(content), response)

    @defer.inlineCallbacks
    def test_rooms_messages_sent(self):
        path = "/rooms/rid1/messages/%s/mid1" % self.user_id
        self._test_invalid_puts(path)

        content = '{"body":"test","msgtype":{"type":"a"}}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code)

        # custom message types
        content = '{"body":"test","msgtype":"test.custom.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads(content), response)

        # sy.text message type
        path = "/rooms/rid1/messages/%s/mid2" % self.user_id
        content = '{"body":"test2","msgtype":"sy.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads(content), response)

        # trying to send message in different user path
        path = "/rooms/rid1/messages/%s/mid2" % ("invalid" + self.user_id)
        content = '{"body":"test2","msgtype":"sy.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(403, code)



