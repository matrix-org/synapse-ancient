# -*- coding: utf-8 -*-
"""Tests REST events for /presence paths."""

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock
import logging

from ..utils import MockHttpServer

from synapse.api.constants import PresenceState
from synapse.server import HomeServer


logging.getLogger().addHandler(logging.NullHandler())


OFFLINE = PresenceState.OFFLINE
BUSY = PresenceState.BUSY
ONLINE = PresenceState.ONLINE


myid = "@apple:test"


class PresenceStateTestCase(unittest.TestCase):

    def setUp(self):
        self.mock_server = MockHttpServer()
        self.mock_handler = Mock(spec=[
            "get_state",
            "set_state",
        ])

        hs = HomeServer("test",
            db_pool=None,
            http_client=None,
            http_server=self.mock_server,
        )

        def _get_user_by_token(token=None):
            return hs.parse_userid(myid)

        hs.get_auth().get_user_by_token = _get_user_by_token

        hs.get_handlers().presence_handler = self.mock_handler

        hs.register_servlets()

        self.u_apple = hs.parse_userid(myid)

    @defer.inlineCallbacks
    def test_get_my_status(self):
        mocked_get = self.mock_handler.get_state
        mocked_get.return_value = defer.succeed(
                {"state": 2, "status_msg": "Available"})

        (code, response) = yield self.mock_server.trigger("GET",
                "/presence/%s/status" % (myid), None)

        self.assertEquals(200, code)
        self.assertEquals({"state": ONLINE, "status_msg": "Available"},
                response)
        mocked_get.assert_called_with(target_user=self.u_apple,
                auth_user=self.u_apple)

    @defer.inlineCallbacks
    def test_set_my_status(self):
        mocked_set = self.mock_handler.set_state
        mocked_set.return_value = defer.succeed(())

        (code, response) = yield self.mock_server.trigger("PUT",
                "/presence/%s/status" % (myid),
                '{"state": 1, "status_msg": "Away"}')

        self.assertEquals(200, code)
        mocked_set.assert_called_with(target_user=self.u_apple,
                auth_user=self.u_apple,
                state={"state": 1, "status_msg": "Away"})


class PresenceListTestCase(unittest.TestCase):

    def setUp(self):
        self.mock_server = MockHttpServer()
        self.mock_handler = Mock(spec=[
            "get_presence_list",
            "send_invite",
            "drop",
        ])

        hs = HomeServer("test",
            db_pool=None,
            http_client=None,
            http_server=self.mock_server,
        )

        def _get_user_by_token(token=None):
            return hs.parse_userid(myid)

        hs.get_auth().get_user_by_token = _get_user_by_token

        hs.get_handlers().presence_handler = self.mock_handler

        hs.register_servlets()

        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")

    @defer.inlineCallbacks
    def test_get_my_list(self):
        self.mock_handler.get_presence_list.return_value = defer.succeed(
                [{"observed_user": self.u_banana}]
        )

        (code, response) = yield self.mock_server.trigger("GET",
                "/presence_list/%s" % (myid), None)

        self.assertEquals(200, code)
        self.assertEquals([{"user_id": "@banana:test"}], response)

    @defer.inlineCallbacks
    def test_invite(self):
        self.mock_handler.send_invite.return_value = defer.succeed(())

        (code, response) = yield self.mock_server.trigger("POST",
                "/presence_list/%s" % (myid),
                """{
                    "invite": ["@banana:test"]
                }""")

        self.assertEquals(200, code)

        self.mock_handler.send_invite.assert_called_with(
                observer_user=self.u_apple, observed_user=self.u_banana)

    @defer.inlineCallbacks
    def test_drop(self):
        self.mock_handler.drop.return_value = defer.succeed(())

        (code, response) = yield self.mock_server.trigger("POST",
                "/presence_list/%s" % (myid),
                """{
                    "drop": ["@banana:test"]
                }""")

        self.assertEquals(200, code)

        self.mock_handler.drop.assert_called_with(
                observer_user=self.u_apple, observed_user=self.u_banana)
