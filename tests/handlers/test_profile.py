# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock
import logging

from synapse.api.errors import AuthError
from synapse.server import HomeServer


logging.getLogger().addHandler(logging.NullHandler())


class ProfileTestCase(unittest.TestCase):
    """ Tests profile management. """

    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "get_profile_displayname",
                    "set_profile_displayname",
                    "get_profile_avatar_url",
                    "set_profile_avatar_url",
                ]),
                http_server=Mock(),
                http_client=Mock(),
            )
        self.datastore = hs.get_datastore()

        self.frank = hs.parse_userid("@1234ABCD:test")
        self.bob   = hs.parse_userid("@4567:test")

        self.handlers = hs.get_handlers()

    @defer.inlineCallbacks
    def test_get_my_name(self):
        mocked_get = self.datastore.get_profile_displayname
        mocked_get.return_value = defer.succeed("Frank")

        displayname = yield self.handlers.profile_handler.get_displayname(
                self.frank)

        self.assertEquals("Frank", displayname)
        mocked_get.assert_called_with("1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_name(self):
        mocked_set = self.datastore.set_profile_displayname
        mocked_set.return_value = defer.succeed(())

        yield self.handlers.profile_handler.set_displayname(
                self.frank, self.frank, "Frank Jr.")

        mocked_set.assert_called_with("1234ABCD", "Frank Jr.")

    @defer.inlineCallbacks
    def test_set_my_name_noauth(self):
        d = self.handlers.profile_handler.set_displayname(self.frank, self.bob,
                "Frank Jr.")

        yield self.assertFailure(d, AuthError)

    @defer.inlineCallbacks
    def test_get_my_avatar(self):
        mocked_get = self.datastore.get_profile_avatar_url
        mocked_get.return_value = defer.succeed("http://my.server/me.png")

        avatar_url = yield self.handlers.profile_handler.get_avatar_url(
                self.frank)

        self.assertEquals("http://my.server/me.png", avatar_url)
        mocked_get.assert_called_with("1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_avatar(self):
        mocked_set = self.datastore.set_profile_avatar_url
        mocked_set.return_value = defer.succeed(())

        yield self.handlers.profile_handler.set_avatar_url(
                self.frank, self.frank, "http://my.server/pic.gif")

        mocked_set.assert_called_with("1234ABCD", "http://my.server/pic.gif")
