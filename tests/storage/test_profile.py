# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from synapse.server import HomeServer


class ProfileStoreTestCase(unittest.TestCase):
    """ Test ProfileStore. """

    def setUp(self):
        self.db_pool = Mock(spec=["runInteraction"])

        hs = HomeServer("test",
                db_pool=self.db_pool)

        self.datastore = hs.get_datastore()

    @defer.inlineCallbacks
    def test_get_displayname(self):
        mocked_ri = self.db_pool.runInteraction
        mocked_ri.return_value = defer.succeed("Frank")

        displayname = yield self.datastore.get_profile_displayname("1234ABCD")

        self.assertEquals("Frank", displayname)
        # Can't easily assert on the [0] positional argument as it's a callable
        self.assertEquals(mocked_ri.call_args[0][1], "1234ABCD")

    @defer.inlineCallbacks
    def test_set_displayname(self):
        mocked_ri = self.db_pool.runInteraction
        mocked_ri.return_value = defer.succeed(())

        yield self.datastore.set_profile_displayname("1234ABCD", "Frank Jr.")

        # Can't easily assert on the [0] positional argument as it's a callable
        self.assertEquals(mocked_ri.call_args[0][1], "1234ABCD")
        self.assertEquals(mocked_ri.call_args[0][2], "Frank Jr.")
