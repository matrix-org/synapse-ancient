# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from synapse.server import HomeServer


class ProfileStoreTestCase(unittest.TestCase):
    """ Test ProfileStore. """

    def setUp(self):
        self.db_pool = Mock(spec=["runInteraction"])
        self.mock_txn = Mock()
        # Our fake runInteraction just runs synchronously inline

        def runInteraction(func, *args, **kwargs):
            return defer.succeed(func(self.mock_txn, *args, **kwargs))
        self.db_pool.runInteraction = runInteraction

        hs = HomeServer("test",
                db_pool=self.db_pool)

        self.datastore = hs.get_datastore()

    @defer.inlineCallbacks
    def test_get_displayname(self):
        mocked_execute = self.mock_txn.execute
        self.mock_txn.rowcount = 1
        mocked_fetchone = self.mock_txn.fetchone
        mocked_fetchone.return_value = ("Frank",)

        displayname = yield self.datastore.get_profile_displayname("1234ABCD")

        self.assertEquals("Frank", displayname)
        mocked_execute.assert_called_with(
                "SELECT displayname FROM profiles WHERE user_id = ?",
                ["1234ABCD"]
        )

    @defer.inlineCallbacks
    def test_set_displayname(self):
        mocked_execute = self.mock_txn.execute
        self.mock_txn.rowcount = 1

        yield self.datastore.set_profile_displayname("1234ABCD", "Frank Jr.")

        mocked_execute.assert_called_with(
                "UPDATE profiles SET displayname = ? WHERE user_id = ?",
                ["Frank Jr.", "1234ABCD"]
        )
