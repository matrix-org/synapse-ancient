# -*- coding: utf-8 -*-
"""Tests REST events for /profile paths."""

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from ..utils import MockHttpServer

from synapse.api.errors import SynapseError, AuthError
from synapse.server import HomeServer

myid = "@1234ABCD:test"
PATH_PREFIX = "/matrix/client/api/v1"

class ProfileTestCase(unittest.TestCase):
    """ Tests profile management. """

    def setUp(self):
        self.mock_server = MockHttpServer(prefix=PATH_PREFIX)
        self.mock_handler = Mock(spec=[
            "get_displayname",
            "set_displayname",
            "get_avatar_url",
            "set_avatar_url",
        ])

        hs = HomeServer("test",
            db_pool=None,
            http_client=None,
            http_server=self.mock_server,
            federation=Mock(),
            replication_layer=Mock(),
        )

        def _get_user_by_token(token=None):
            return hs.parse_userid(myid)

        hs.get_auth().get_user_by_token = _get_user_by_token

        hs.get_handlers().profile_handler = self.mock_handler

        hs.register_servlets()

    @defer.inlineCallbacks
    def test_get_my_name(self):
        mocked_get = self.mock_handler.get_displayname
        mocked_get.return_value = defer.succeed("Frank")

        (code, response) = yield self.mock_server.trigger("GET",
                "/profile/%s/displayname" % (myid), None)

        self.assertEquals(200, code)
        self.assertEquals({"displayname": "Frank"}, response)
        self.assertEquals(mocked_get.call_args[0][0].localpart, "1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_name(self):
        mocked_set = self.mock_handler.set_displayname
        mocked_set.return_value = defer.succeed(())

        (code, response) = yield self.mock_server.trigger("PUT",
                "/profile/%s/displayname" % (myid),
                '{"displayname": "Frank Jr."}')

        self.assertEquals(200, code)
        self.assertEquals(mocked_set.call_args[0][0].localpart, "1234ABCD")
        self.assertEquals(mocked_set.call_args[0][1].localpart, "1234ABCD")
        self.assertEquals(mocked_set.call_args[0][2], "Frank Jr.")

    @defer.inlineCallbacks
    def test_set_my_name_noauth(self):
        mocked_set = self.mock_handler.set_displayname
        mocked_set.side_effect = AuthError(400, "message")

        (code, response) = yield self.mock_server.trigger("PUT",
                "/profile/%s/displayname" % ("@4567:test"), '"Frank Jr."')

        self.assertTrue(400 <= code < 499,
                msg="code %d is in the 4xx range" % (code))

    @defer.inlineCallbacks
    def test_get_other_name(self):
        mocked_get = self.mock_handler.get_displayname
        mocked_get.return_value = defer.succeed("Bob")

        (code, response) = yield self.mock_server.trigger("GET",
                "/profile/%s/displayname" % ("@opaque:elsewhere"), None)

        self.assertEquals(200, code)
        self.assertEquals({"displayname": "Bob"}, response)

    @defer.inlineCallbacks
    def test_set_other_name(self):
        mocked_set = self.mock_handler.set_displayname
        mocked_set.side_effect = SynapseError(400, "message")

        (code, response) = yield self.mock_server.trigger("PUT",
                "/profile/%s/displayname" % ("@opaque:elsewhere"), None)

        self.assertTrue(400 <= code <= 499,
                msg="code %d is in the 4xx range" % (code))

    @defer.inlineCallbacks
    def test_get_my_avatar(self):
        mocked_get = self.mock_handler.get_avatar_url
        mocked_get.return_value = defer.succeed("http://my.server/me.png")

        (code, response) = yield self.mock_server.trigger("GET",
                "/profile/%s/avatar_url" % (myid), None)

        self.assertEquals(200, code)
        self.assertEquals({"avatar_url": "http://my.server/me.png"}, response)
        self.assertEquals(mocked_get.call_args[0][0].localpart, "1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_avatar(self):
        mocked_set = self.mock_handler.set_avatar_url
        mocked_set.return_value = defer.succeed(())

        (code, response) = yield self.mock_server.trigger("PUT",
                "/profile/%s/avatar_url" % (myid),
                '{"avatar_url": "http://my.server/pic.gif"}')

        self.assertEquals(200, code)
        self.assertEquals(mocked_set.call_args[0][0].localpart, "1234ABCD")
        self.assertEquals(mocked_set.call_args[0][1].localpart, "1234ABCD")
        self.assertEquals(mocked_set.call_args[0][2],
                "http://my.server/pic.gif")
