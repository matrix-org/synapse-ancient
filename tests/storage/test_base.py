# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock, call

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

        yield self.datastore._simple_insert(
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

        yield self.datastore._simple_insert(
                table="tablename",
                # Use OrderedDict() so we can assert on the SQL generated
                values=OrderedDict([("colA", 1), ("colB", 2), ("colC", 3)])
        )

        self.mock_txn.execute.assert_called_with(
                "INSERT INTO tablename (colA, colB, colC) VALUES(?, ?, ?)",
                [1, 2, 3]
        )

    @defer.inlineCallbacks
    def test_select_one_1col(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = ("Value",)

        value = yield self.datastore._simple_select_one_onecol(
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
    def test_select_one_3col(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = (1, 2, 3)

        ret = yield self.datastore._simple_select_one(
                table="tablename",
                keyvalues={"keycol": "TheKey"},
                retcols=["colA", "colB", "colC"]
        )

        self.assertEquals({"colA": 1, "colB": 2, "colC": 3}, ret)
        self.mock_txn.execute.assert_called_with(
                "SELECT colA, colB, colC FROM tablename WHERE keycol = ?",
                ["TheKey"]
        )

    @defer.inlineCallbacks
    def test_select_one_missing(self):
        self.mock_txn.rowcount = 0
        self.mock_txn.fetchone.return_value = None

        ret = yield self.datastore._simple_select_one(
                table="tablename",
                keyvalues={"keycol": "Not here"},
                retcols=["colA"],
                allow_none=True
        )

        self.assertFalse(ret)

    @defer.inlineCallbacks
    def test_select_list(self):
        self.mock_txn.rowcount = 3;
        self.mock_txn.fetchall.return_value = ((1,), (2,), (3,))
        self.mock_txn.description = (
                ("colA", None, None, None, None, None, None),
        )

        ret = yield self.datastore._simple_select_list(
                table="tablename",
                keyvalues={"keycol": "A set"},
                retcols=["colA"],
        )

        self.assertEquals([{"colA": 1}, {"colA": 2}, {"colA": 3}], ret)
        self.mock_txn.execute.assert_called_with(
                "SELECT colA FROM tablename WHERE keycol = ?",
                ["A set"]
        )

    @defer.inlineCallbacks
    def test_update_one_1col(self):
        self.mock_txn.rowcount = 1

        yield self.datastore._simple_update_one(
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

        yield self.datastore._simple_update_one(
                table="tablename",
                keyvalues=OrderedDict([("colA", 1), ("colB", 2)]),
                updatevalues=OrderedDict([("colC", 3), ("colD", 4)])
        )

        self.mock_txn.execute.assert_called_with(
                "UPDATE tablename SET colC = ?, colD = ? WHERE " +
                    "colA = ? AND colB = ?",
                [3, 4, 1, 2]
        )

    @defer.inlineCallbacks
    def test_update_one_with_return(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = ("Old Value",)

        ret = yield self.datastore._simple_update_one(
                table="tablename",
                keyvalues={"keycol": "TheKey"},
                updatevalues={"columname": "New Value"},
                retcols=["columname"]
        )

        self.assertEquals({"columname": "Old Value"}, ret)
        self.mock_txn.execute.assert_has_calls([
                call('SELECT columname FROM tablename WHERE keycol = ?',
                    ['TheKey']),
                call("UPDATE tablename SET columname = ? WHERE keycol = ?",
                    ["New Value", "TheKey"])
        ])

    @defer.inlineCallbacks
    def test_delete_one(self):
        self.mock_txn.rowcount = 1

        yield self.datastore._simple_delete_one(
                table="tablename",
                keyvalues={"keycol": "Go away"},
        )

        self.mock_txn.execute.assert_called_with(
                "DELETE FROM tablename WHERE keycol = ?",
                ["Go away"]
        )
