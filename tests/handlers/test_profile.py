# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from synapse.api.auth import Auth
from synapse.api.errors import AuthError
from synapse.server import HomeServer


class ProfileTestCase(unittest.TestCase):
    """ Tests profile management. """

    def setUp(self):
        self.db_pool = Mock(spec=["runInteraction"])

        hs = HomeServer("test",
                db_pool=self.db_pool)

        self.frank = hs.parse_userid("@1234ABCD:test")
        self.bob   = hs.parse_userid("@4567:test")

        self.handlers = hs.get_handlers()

    @defer.inlineCallbacks
    def test_get_my_name(self):
        mocked_ri = self.db_pool.runInteraction
        mocked_ri.return_value = defer.succeed("Frank")

        displayname = yield self.handlers.profile_handler.get_displayname(
                self.frank)

        self.assertEquals("Frank", displayname)
        # Can't easily assert on the [0] positional argument as it's a callable
        self.assertEquals(mocked_ri.call_args[0][1], "1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_name(self):
        mocked_ri = self.db_pool.runInteraction
        mocked_ri.return_value = defer.succeed(())

        yield self.handlers.profile_handler.set_displayname(
                self.frank, self.frank, "Frank Jr.")

        self.assertEquals(mocked_ri.call_args[0][1], "1234ABCD")
        self.assertEquals(mocked_ri.call_args[0][2], "Frank Jr.")

    @defer.inlineCallbacks
    def test_set_my_name_noauth(self):
        d = self.handlers.profile_handler.set_displayname(self.frank, self.bob,
                "Frank Jr.")

        yield self.assertFailure(d, AuthError)
