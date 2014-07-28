# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock

from collections import OrderedDict

from synapse.server import HomeServer
from synapse.storage._base import SQLBaseStore


class SQLBaseStoreTestCase(unittest.TestCase):
    """ Test the "simple" SQL generating methods in SQLBaseStore. """

    def setUp(self):
        self.db_pool = Mock(spec=["runInteraction"])
        self.mock_txn = Mock()
        # Our fake runInteraction just runs synchronously inline

        def runInteraction(func, *args, **kwargs):
            return defer.succeed(func(self.mock_txn, *args, **kwargs))
        self.db_pool.runInteraction = runInteraction

        hs = HomeServer("test",
                db_pool=self.db_pool)

        self.datastore = SQLBaseStore(hs)

    @defer.inlineCallbacks
    def test_insert_1col(self):
        self.mock_txn.rowcount = 1

        yield self.datastore.interact_simple_insert(
                table="tablename",
                values={"columname": "Value"}
        )

        self.mock_txn.execute.assert_called_with(
                "INSERT INTO tablename (columname) VALUES(?)",
                ["Value"]
        )

    @defer.inlineCallbacks
    def test_insert_3cols(self):
        self.mock_txn.rowcount = 1

        yield self.datastore.interact_simple_insert(
                table="tablename",
                # Use OrderedDict() so we can assert on the SQL generated
                values=OrderedDict([("colA", 1), ("colB", 2), ("colC", 3)])
        )

        self.mock_txn.execute.assert_called_with(
                "INSERT INTO tablename (colA, colB, colC) VALUES(?, ?, ?)",
                [1, 2, 3]
        )

    @defer.inlineCallbacks
    def test_select_one_one(self):
        self.mock_txn.rowcount = 1
        mocked_fetchone = self.mock_txn.fetchone
        mocked_fetchone.return_value = ("Value",)

        value = yield self.datastore.interact_simple_select_one_one(
                table="tablename",
                keyvalues={"keycol": "TheKey"},
                retcol="retcol"
        )

        self.assertEquals("Value", value)
        self.mock_txn.execute.assert_called_with(
                "SELECT retcol FROM tablename WHERE keycol = ?",
                ["TheKey"]
        )

    @defer.inlineCallbacks
    def test_update_one_1col(self):
        self.mock_txn.rowcount = 1

        yield self.datastore.interact_simple_update_one(
                table="tablename",
                keyvalues={"keycol": "TheKey"},
                updatevalues={"columnname": "New Value"}
        )

        self.mock_txn.execute.assert_called_with(
                "UPDATE tablename SET columnname = ? WHERE keycol = ?",
                ["New Value", "TheKey"]
        )

    @defer.inlineCallbacks
    def test_update_one_4cols(self):
        self.mock_txn.rowcount = 1

        yield self.datastore.interact_simple_update_one(
                table="tablename",
                keyvalues=OrderedDict([("colA", 1), ("colB", 2)]),
                updatevalues=OrderedDict([("colC", 3), ("colD", 4)])
        )

        self.mock_txn.execute.assert_called_with(
                "UPDATE tablename SET colC = ?, colD = ? WHERE " +
                    "colA = ? AND colB = ?",
                [3, 4, 1, 2]
        )