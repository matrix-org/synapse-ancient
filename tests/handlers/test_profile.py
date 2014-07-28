# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from synapse.api.errors import AuthError
from synapse.server import HomeServer


class ProfileTestCase(unittest.TestCase):
    """ Tests profile management. """

    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "get_profile_displayname",
                    "set_profile_displayname",
                ]))
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
        self.assertEquals(mocked_get.call_args[0][0], "1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_name(self):
        mocked_set = self.datastore.set_profile_displayname
        mocked_set.return_value = defer.succeed(())

        yield self.handlers.profile_handler.set_displayname(
                self.frank, self.frank, "Frank Jr.")

        self.assertEquals(mocked_set.call_args[0][0], "1234ABCD")
        self.assertEquals(mocked_set.call_args[0][1], "Frank Jr.")

    @defer.inlineCallbacks
    def test_set_my_name_noauth(self):
        d = self.handlers.profile_handler.set_displayname(self.frank, self.bob,
                "Frank Jr.")

        yield self.assertFailure(d, AuthError)
