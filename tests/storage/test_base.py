# -*- coding: utf-8 -*-

import unittest

from mock import Mock, call

from collections import OrderedDict

from synapse.server import HomeServer
from synapse.storage._base import SQLBaseStore


class SQLBaseStoreTestCase(unittest.TestCase):
    """ Test the "simple" SQL generating methods in SQLBaseStore. """

    def setUp(self):
        self.db_pool = Mock(spec=["runInteraction"])
        self.mock_txn = Mock()

        hs = HomeServer("test", db_pool=self.db_pool)

        self.datastore = SQLBaseStore(hs)

    def test_insert_1col(self):
        self.mock_txn.rowcount = 1

        self.datastore._simple_insert(
            self.mock_txn,
            table="tablename",
            values={"columname": "Value"}
        )

        self.mock_txn.execute.assert_called_with(
            "INSERT INTO tablename (columname) VALUES(?)",
            ["Value"]
        )

    def test_insert_3cols(self):
        self.mock_txn.rowcount = 1

        self.datastore._simple_insert(
            self.mock_txn,
            table="tablename",
            # Use OrderedDict() so we can assert on the SQL generated
            values=OrderedDict([("colA", 1), ("colB", 2), ("colC", 3)])
        )

        self.mock_txn.execute.assert_called_with(
            "INSERT INTO tablename (colA, colB, colC) VALUES(?, ?, ?)",
            [1, 2, 3]
        )

    def test_select_one_1col(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = ("Value",)

        value = self.datastore._simple_select_one_onecol(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "TheKey"},
            retcol="retcol"
        )

        self.assertEquals("Value", value)
        self.mock_txn.execute.assert_called_with(
            "SELECT retcol FROM tablename WHERE keycol = ?",
            ["TheKey"]
        )

    def test_select_one_3col(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = (1, 2, 3)

        ret = self.datastore._simple_select_one(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "TheKey"},
            retcols=["colA", "colB", "colC"]
        )

        self.assertEquals({"colA": 1, "colB": 2, "colC": 3}, ret)
        self.mock_txn.execute.assert_called_with(
            "SELECT colA, colB, colC FROM tablename WHERE keycol = ?",
            ["TheKey"]
        )

    def test_select_one_missing(self):
        self.mock_txn.rowcount = 0
        self.mock_txn.fetchone.return_value = None

        ret = self.datastore._simple_select_one(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "Not here"},
            retcols=["colA"],
            allow_none=True
        )

        self.assertFalse(ret)

    def test_select_list(self):
        self.mock_txn.rowcount = 3;
        self.mock_txn.fetchall.return_value = ((1,), (2,), (3,))
        self.mock_txn.description = (
            ("colA", None, None, None, None, None, None),
        )

        ret = self.datastore._simple_select_list(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "A set"},
            retcols=["colA"],
        )

        self.assertEquals([{"colA": 1}, {"colA": 2}, {"colA": 3}], ret)
        self.mock_txn.execute.assert_called_with(
            "SELECT colA FROM tablename WHERE keycol = ?",
            ["A set"]
        )

    def test_update_one_1col(self):
        self.mock_txn.rowcount = 1

        self.datastore._simple_update_one(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "TheKey"},
            updatevalues={"columnname": "New Value"}
        )

        self.mock_txn.execute.assert_called_with(
                "UPDATE tablename SET columnname = ? WHERE keycol = ?",
                ["New Value", "TheKey"]
        )

    def test_update_one_4cols(self):
        self.mock_txn.rowcount = 1

        self.datastore._simple_update_one(
            self.mock_txn,
            table="tablename",
            keyvalues=OrderedDict([("colA", 1), ("colB", 2)]),
            updatevalues=OrderedDict([("colC", 3), ("colD", 4)])
        )

        self.mock_txn.execute.assert_called_with(
                "UPDATE tablename SET colC = ?, colD = ? WHERE " +
                    "colA = ? AND colB = ?",
                [3, 4, 1, 2]
        )

    def test_update_one_with_return(self):
        self.mock_txn.rowcount = 1
        self.mock_txn.fetchone.return_value = ("Old Value",)

        ret = yield self.datastore._simple_update_one(
            self.mock_txn,
            table="tablename",
            keyvalues={"keycol": "TheKey"},
            updatevalues={"columname": "New Value"},
            retcols=["columname"]
        )

        self.assertEquals({"columname": "Old Value"}, ret)
        self.mock_txn.execute.assert_has_calls([
            call(
                'SELECT columname FROM tablename WHERE keycol = ?',
                ['TheKey']
            ),
            call(
                "UPDATE tablename SET columname = ? WHERE keycol = ?",
                ["New Value", "TheKey"]
            )
        ])

    def test_delete_one(self):
        self.mock_txn.rowcount = 1

        self.datastore._simple_delete_one(
            self.mock_txn,
                table="tablename",
                keyvalues={"keycol": "Go away"},
        )

        self.mock_txn.execute.assert_called_with(
                "DELETE FROM tablename WHERE keycol = ?",
                ["Go away"]
        )
