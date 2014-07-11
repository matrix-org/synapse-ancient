# -*- coding: utf-8 -*-
"""This module contains metadata about the tables we use, as well as defining
convenience types and functions to help query the tables.
"""

from collections import namedtuple


_select_where_clause = "SELECT %s FROM %s WHERE %s"
_select_clause = "SELECT %s FROM %s"
_insert_clause = "INSERT OR REPLACE INTO %s (%s) VALUES (%s)"


class Table(object):
    """ A base class used to store information about a particular table.
    """

    table_name = None
    """ str: The name of the table """

    fields = None
    """ list: The field names """

    EntryType = None
    """ Type: A tuple type used to decode the results """

    @classmethod
    def select_statement(cls, where_clause=None):
        """
        Args:
            where_clause (str): The WHERE clause to use.

        Returns:
            str: An SQL statement to select rows from the table with the given
            WHERE clause.
        """
        if where_clause:
            return _select_where_clause % (
                ", ".join(cls.fields),
                cls.table_name,
                where_clause
            )
        else:
            return _select_clause % (
                ", ".join(cls.fields),
                cls.table_name,
            )

    @classmethod
    def insert_statement(cls):
        return _insert_clause % (
            cls.table_name,
            ", ".join(cls.fields),
            ", ".join(["?"] * len(cls.fields)),
        )

    @classmethod
    def decode_results(cls, results):
        """ Given an iterable of tuples, return a list of `EntryType`
        Args:
            results (list): The results list to convert to `EntryType`

        Returns:
            list: A list of `EntryType`
        """
        return [cls.EntryType(*row) for row in results]

    @classmethod
    def get_fields_string(cls, prefix=None):
        if prefix:
            to_join = ("%s.%s" % (prefix, f) for f in cls.fields)
        else:
            to_join = cls.fields

        return ", ".join(to_join)


class ReceivedTransactionsTable(Table):
    table_name = "received_transactions"

    fields = [
        "transaction_id",
        "origin",
        "ts",
        "response_code",
        "response_json",
        "has_been_referenced",
    ]

    EntryType = namedtuple("ReceivedTransactionsEntry", fields)


class SentTransactions(Table):
    table_name = "sent_transactions"

    fields = [
        "id",
        "transaction_id",
        "destination",
        "ts",
        "response_code",
        "response_json",
    ]

    EntryType = namedtuple("SentTransactionsEntry", fields)


class TransactionsToPduTable(Table):
    table_name = "transaction_id_to_pdu"

    fields = [
        "transaction_id",
        "destination",
        "pdu_id",
        "pdu_origin",
    ]

    EntryType = namedtuple("TransactionsToPduEntry", fields)


class PdusTable(Table):
    table_name = "pdus"

    fields = [
        "pdu_id",
        "origin",
        "context",
        "pdu_type",
        "ts",
        "depth",
        "is_state",
        "content_json",
        "unrecognized_keys",
        "outlier",
        "have_processed",
    ]

    EntryType = namedtuple("PdusEntry", fields)


class StatePdusTable(Table):
    table_name = "state_pdus"

    fields = [
        "pdu_id",
        "origin",
        "context",
        "pdu_type",
        "state_key",
        "power_level",
        "prev_state_id",
        "prev_state_origin",
    ]

    EntryType = namedtuple("StatePdusEntry", fields)


class CurrentStateTable(Table):
    table_name = "current_state"

    fields = [
        "pdu_id",
        "origin",
        "context",
        "pdu_type",
        "state_key",
    ]

    EntryType = namedtuple("CurrentStateEntry", fields)


class PduDestinationsTable(Table):
    table_name = "pdu_destinations"

    fields = [
        "pdu_id",
        "origin",
        "destination",
        "delivered_ts",
    ]

    EntryType = namedtuple("PduDestinationsEntry", fields)


class PduEdgesTable(Table):
    table_name = "pdu_edges"

    fields = [
        "pdu_id",
        "origin",
        "prev_pdu_id",
        "prev_origin",
        "context"
    ]

    EntryType = namedtuple("PduEdgesEntry", fields)


class PduForwardExtremitiesTable(Table):
    table_name = "pdu_forward_extremities"

    fields = [
        "pdu_id",
        "origin",
        "context",
    ]

    EntryType = namedtuple("PduForwardExtremitiesEntry", fields)


class PduBackwardExtremitiesTable(Table):
    table_name = "pdu_backward_extremities"

    fields = [
        "pdu_id",
        "origin",
        "context",
    ]

    EntryType = namedtuple("PduBackwardExtremitiesEntry", fields)


class ContextDepthTable(Table):
    table_name = "context_depth"

    fields = [
        "context",
        "min_depth",
    ]

    EntryType = namedtuple("ContextDepthEntry", fields)


class RoomDataTable(Table):
    table_name = "room_data"

    fields = [
        "id",
        "room_id",
        "path",
        "content"
    ]

    EntryType = namedtuple("RoomDataEntry", fields)


class RoomMemberTable(Table):
    table_name = "room_memberships"

    fields = [
        "id",
        "user_id",
        "room_id",
        "membership",
        "content"
    ]

    EntryType = namedtuple("RoomMemberEntry", fields)


class JoinHelper(object):
    """ Used to help do joins on tables by looking at the tables' fields and
    creating a list of unique fields to use with SELECTs and a namedtuple
    to dump the results into.

    Attributes:
        taples (list): List of `Table` classes
        EntryType (type)
    """

    def __init__(self, *tables):
        self.tables = tables

        res = []
        for table in self.tables:
            res += [f for f in table.fields if f not in res]

        self.EntryType = namedtuple("JoinHelperEntry", res)

    def get_fields(self, **prefixes):
        """Get a string representing a list of fields for use in SELECT
        statements with the given prefixes applied to each.

        For example::

            JoinHelper(PdusTable, StateTable).get_fields(
                PdusTable="pdus",
                StateTable="state"
            )
        """
        res = []
        for field in self.EntryType._fields:
            for table in self.tables:
                if field in table.fields:
                    res.append("%s.%s" % (prefixes[table.__name__], field))
                    break

        return ", ".join(res)

    def decode_results(self, rows):
        return [self.EntryType(*row) for row in rows]
