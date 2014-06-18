# -*- coding: utf-8 -*-

from collections import namedtuple


_select_where_clause = "SELECT %s FROM %s WHERE %s"
_select_clause = "SELECT %s FROM %s"
_insert_clause = "INSERT INTO %s (%s) VALUES (%s)"


class Table(object):
    """ A base class used to store information about a particular table.
    """

    table_name = None
    """ str: The name of the table """

    fields = None
    """ list: The field names """

    EntryType = None
    """ Type: A tuple type used to decode the results """

    CoumnNames = None
    """ collections.namedtuple: A trivial convenience mapping from
            column names -> column names.
    """

    @classmethod
    def select_statement(clz, where_clause=None):
        """
        Args:
            where_clause (str): The WHERE clause to use.

        Returns:
            str: An SQL statement to select rows from the table with the given
            WHERE clause.
        """
        if where_clause:
            return _select_where_clause % (
                    ", ".join(clz.fields),
                    clz.table_name,
                    where_clause
                )
        else:
            return _select_clause

    @classmethod
    def insert_statement(clz):
        return _insert_clause % (
                clz.table_name,
                ", ".join(clz.fields),
                ", ".join(["?"] * len(clz.fields)),
            )

    @classmethod
    def decode_results(clz, results):
        """ Given an iterable of tuples, return a list of `EntryType`
        Args:
            results (list): The results list to convert to `EntryType`

        Returns:
            list: A list of `EntryType`
        """
        return [clz.EntryType(*row) for row in results]

    @staticmethod
    def generate_where(*field_names):
        return " AND ".join(["%s = ?" % f for f in field_names])


class ReceivedTransactionsTable(Table):
    table_name = "received_transactions"

    fields = [
        "transaction_id",
        "origin",
        "ts",
        "response_code",
        "response_json",
    ]

    EntryType = namedtuple("ReceivedTransactionsEntry", fields)

    CoumnNames = EntryType(*fields)


class SentTransactions(Table):
    table_name = "sent_transactions"

    fields = [
        "id",
        "transaction_id",
        "destination",
        "ts",
        "response_code",
        "response_json",
        "have_referenced",
    ]

    EntryType = namedtuple("SentTransactionsEntry", fields)

    CoumnNames = EntryType(*fields)


class TransactionsToPduTable(Table):
    table_name = "transaction_id_to_pdu"

    fields = [
        "transaction_id",
        "destination",
        "pdu_id",
    ]

    EntryType = namedtuple("TransactionsToPduEntry", fields)

    CoumnNames = EntryType(*fields)


class PdusTable(Table):
    table_name = "pdus"

    fields = [
        "pdu_id",
        "context",
        "pdu_type",
        "origin",
        "ts",
        "is_state",
        "state_key",
        "content_json",
        "unrecognized_keys",
    ]

    EntryType = namedtuple("PdusEntry", fields)

    CoumnNames = EntryType(*fields)


class StatePdusTable(Table):
    table_name = "state_pdus"

    fields = [
        "pdu_id",
        "origin",
        "context",
        "pdu_type",
        "state_key",
    ]

    EntryType = namedtuple("StatePdusEntry", fields)

    CoumnNames = EntryType(*fields)


class PduDestinationsTable(Table):
    table_name = "pdu_destinations"

    fields = [
        "pdu_id",
        "origin",
        "destination",
        "delivered_ts",
    ]

    EntryType = namedtuple("PduDestinationsEntry", fields)

    CoumnNames = EntryType(*fields)


class PduEdgesTable(Table):
    table_name = "pdu_edges"

    fields = [
        "pdu_id",
        "origin",
        "prev_pdu_id",
        "prev_origin",
    ]

    EntryType = namedtuple("PduEdgesEntry", fields)

    CoumnNames = EntryType(*fields)


class PduForwardExtremetiesTable(Table):
    table_name = "pdu_forward_extremeties"

    fields = [
        "pdu_id",
        "origin",
        "context",
    ]

    EntryType = namedtuple("PduForwardExtremetiesEntry", fields)

    CoumnNames = EntryType(*fields)
