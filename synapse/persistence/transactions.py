# -*- coding: utf-8 -*-
"""This module is where we define the different queries we can run on the
database.

All queries
"""

from .tables import (
    ReceivedTransactionsTable, SentTransactions,
    TransactionsToPduTable, PdusTable, StatePdusTable, PduEdgesTable,
    PduForwardExtremitiesTable, PduBackwardExtremitiesTable, CurrentStateTable,
    ContextDepthTable
)
from ..util import DbPool

from collections import namedtuple

import logging


logger = logging.getLogger(__name__)

PduTuple = namedtuple(
    "PduTuple",
    ("pdu_entry", "state_entry", "prev_pdu_list")
)
TransactionTuple = namedtuple("TransactionTuple", ("tx_entry", "prev_ids"))
PduIdTuple = namedtuple("PduIdTuple", ("pdu_id", "origin"))

pdu_state_fields = (
    PdusTable.fields
    + [r for r in StatePdusTable.fields if r not in PdusTable.fields]
)
PduAndStateTuple = namedtuple("PduAndStateTuple", pdu_state_fields)


def run_interaction(transaction_func, *args, **kwargs):
    """ Takes a function that queires the database and runs it in a dedicated
    thread.

    Args:
        transaction_func (function): The function to run. Will get passed, as
            the first parameter, a transaction object to use to talk to the
            database. This get's run in a seperate thread.

        *args: Extra arguments to pass to `transaction_func`
        **kwargs: Extra keyword arguments to pass to `transaction_func`

    Returns:
        Deferred: Resolves with the result of `transaction_func`.
    """
    return DbPool.get().runInteraction(
        transaction_func, *args, **kwargs)


class TransactionQueries(object):
    """A collection of queries that deal mainly with transactions.

    All functions are executed synchrously. To run them in an asynchronous
    fashion use `run_interaction`
    """

    @classmethod
    def get_response_for_received(cls, txn, transaction_id, origin):
        """For an incoming transaction from a given origin, check if we have
        already responded to it. If so, return the response code and response
        body (as a dict).

        Args:
            txn
            transaction_id (str)
            origin(str)

        Returns:
            tuple: None if we have not previously responded to
            this transaction or a 2-tuple of (int, dict)
        """
        result = cls._get_received_interaction(txn, transaction_id, origin)

        if result and result.response_code:
            return (result.response_code, result.response_json)
        else:
            return None

    @classmethod
    def insert_received(cls, txn, tx_tuple):
        """Persist an incoming transaction.

        Args:
            txn
            tx_tuple (TransactionTuple)
        """
        return cls._insert_interaction(txn, tx_tuple)

    @classmethod
    def set_recieved_txn_response(cls, txn, transaction_id, origin, code,
                                  response_json):
        """Persist the response we returened for an incoming transaction, and
        should return for subsequent transactions with the same transaction_id
        and origin.

        Args:
            txn
            transaction_id (str)
            origin (str)
            code (int)
            response_json (str)
        """
        return cls._set_recieved_response_interaction(
            txn, transaction_id, origin, code, response_json)

    @classmethod
    def prep_send_transaction(cls, txn, transaction_id, destination, ts,
                              pdu_list):
        """Persists an outgoing transaction and calculates the values for the
        previous transaction id list.

        This should be called before sending the transaction so that it has the
        correct value for the `prev_ids` key.

        Args:
            txn
            transaction_id (str)
            destination (str)
            ts (int)
            pdu_list (list)

        Returns:
            list: A list of previous transaction ids.
        """
        return cls._prep_send_transaction_interaction(
            txn,
            transaction_id, destination, ts, pdu_list)

    @classmethod
    def delivered_txn(cls, txn, transaction_id, destination,
                      code, response_json):
        """Persists the response for an outgoing transaction.

        Args:
            txn
            transaction_id (str)
            destination (str)
            code (int)
            response_json (str)
        """
        return cls._delivered_txn_interaction(
            txn, transaction_id, destination, code, response_json)

    @classmethod
    def get_transactions_after(cls, txn, transaction_id, destination):
        """Get all transactions after a given local transaction_id.

        Args:
            txn
            transaction_id (str)
            destination (str)

        Returns:
            list: A list of `ReceivedTransactionsTable.EntryType`
        """
        return cls._get_transactions_after_interaction(
            txn, transaction_id, destination)

    @staticmethod
    def _get_sent_interaction(txn, transaction_id, destination):
        where_clause = "transaction_id = ? AND destination = ?"
        query = SentTransactions.select_statement(where_clause)

        txn.execute(query, (transaction_id,))

        results = SentTransactions.decode_results(txn.fetchall())

        if len(results) == 0:
            return None
        else:
            return results[1]

    @staticmethod
    def _get_received_interaction(txn, transaction_id, origin):
        where_clause = "transaction_id = ? AND origin = ?"
        query = ReceivedTransactionsTable.select_statement(where_clause)

        txn.execute(query, (transaction_id, origin))

        results = ReceivedTransactionsTable.decode_results(txn.fetchall())

        if len(results) == 0:
            return None
        else:
            return results[1]

    @staticmethod
    def _insert_received_interaction(txn, tx_tuple):
        query = ReceivedTransactionsTable.insert_statement()

        txn.execute(query, tx_tuple.tx_entry)

        query = (
            "UPDATE %s SET has_been_referenced = 1 "
            "WHERE transaction_id = ? AND orign = ?"
        ) % ReceivedTransactionsTable.table_name

        origin = tx_tuple.tx_entry.origin

        txn.executemany(query, [
            (tx_id, origin) for tx_id in tx_tuple.prev_ids
        ])

    @staticmethod
    def _set_recieved_response_interaction(txn, transaction_id, origin,
                                           code, response_json):
        query = (
            "UPDATE %s "
            "SET response_code = ?, response_json = ? "
            "WHERE transaction_id = ? AND origin = ?"
        ) % ReceivedTransactionsTable.table_name

        txn.execute(query, (code, response_json, transaction_id, origin))

    @staticmethod
    def _delivered_txn_interaction(txn, transaction_id, destination,
                                   code, response_json):
        # Say what response we got.
        query = (
            "UPDATE %s "
            "SET response_code = ?, response_json = ? "
            "WHERE transaction_id = ? AND destination = ?"
        ) % SentTransactions.table_name

        txn.execute(query, (code, response_json, transaction_id, destination))

    @staticmethod
    def _prep_send_transaction_interaction(txn, transaction_id, destination,
                                           ts, pdu_list):
        # First we find out what the prev_txs should be.
        # Since we know that we are only sending one transaction at a time,
        # we can simply take the last one.
        query = "%s ORDER BY id DESC LIMIT 1" % (
                SentTransactions.select_statement("destination = ?"),
            )

        results = txn.execute(query, (destination,))
        results = SentTransactions.decode_results(results)

        prev_txns = [r.transaction_id for r in results]

        # Actually add the new transaction to the sent_transactions table.

        query = SentTransactions.insert_statement()
        txn.execute(query, SentTransactions.EntryType(
            None,
            transaction_id=transaction_id,
            destination=destination,
            ts=ts,
            response_code=0,
            response_json=None
        ))

        # Update the tx id -> pdu id mapping

        values = [
            (transaction_id, destination, pdu[0], pdu[1])
            for pdu in pdu_list
        ]

        logger.debug("Inserting: %s", repr(values))

        query = TransactionsToPduTable.insert_statement()
        txn.executemany(query, values)

        return prev_txns

    @classmethod
    def _get_transactions_after_interaction(cls, txn, transaction_id,
                                            destination):
        where = (
            "destination = ? AND id > (select id FROM %s WHERE "
            "transaction_id = ? AND destination = ?)"
        ) % (
            SentTransactions.table_name
        )
        query = SentTransactions.select_statement(where)

        txn.execute(query, (destination, transaction_id, destination))

        return ReceivedTransactionsTable.decode_results(txn.fetchall())


class PduQueries(object):
    """A collection of queries for handling PDUs.

    All functions are executed synchrously. To run them in an asynchronous
    fashion use `run_interaction`
    """

    @classmethod
    def get_pdu(cls, txn, pdu_id, origin):
        """Given a pdu_id and origin, get a PDU.

        Args:
            txn
            pdu_id (str)
            origin (str)

        Returns:
            PduTuple: If the pdu does not exist in the database, returns None
        """
        return cls._get_pdu_interaction(txn, pdu_id, origin)

    @classmethod
    def get_current_state(cls, txn, context):
        """Get a list of PDUs that represent the current state for a given
        context

        Args:
            txn
            context (str)

        Returns:
            list: A list of PduTuples
        """
        return cls._get_current_state_interaction(txn, context)

    @classmethod
    def insert(cls, txn, prev_pdus, **cols):
        """Inserts a (non-state) PDU into the database.

        Args:
            txn,
            prev_pdus (list)
            **cols: The columns to insert into the PdusTable.
        """
        entry = PdusTable.EntryType(
            **{k: cols.get(k, None) for k in PdusTable.fields}
        )
        return cls._insert_interaction(txn, entry, prev_pdus)

    @classmethod
    def insert_state(cls, txn, prev_pdus, **cols):
        """Inserts a state PDU into the database

        Args:
            txn,
            prev_pdus (list)
            **cols: The columns to insert into the PdusTable and StatePdusTable
        """
        pdu_entry = PdusTable.EntryType(
            **{k: cols.get(k, None) for k in PdusTable.fields}
        )
        state_entry = StatePdusTable.EntryType(
            **{k: cols.get(k, None) for k in StatePdusTable.fields}
        )

        logger.debug("Inserting pdu: %s", repr(pdu_entry))
        logger.debug("Inserting state: %s", repr(state_entry))

        return cls._insert_state_interaction(
            txn,
            pdu_entry, state_entry, prev_pdus)

    @classmethod
    def mark_as_processed(cls, txn, pdu_id, pdu_origin):
        """Mark a received PDU as processed.

        Args:
            txn
            pdu_id (str)
            pdu_origin (str)
        """
        return cls._mark_as_processed_interaction(txn, pdu_id, pdu_origin)

    @classmethod
    def get_prev_pdus(cls, txn, context):
        """Get's a list of the most current pdus for a given context. This is
        used when we are sending a Pdu and need to fill out the `prev_pdus`
        key

        Args:
            txn
            context
        """
        return cls._get_prev_pdus_interaction(txn, context)

    @classmethod
    def get_after_transaction(cls, txn, transaction_id, destination,
                              local_server):
        """For a given local transaction_id that we sent to a given destination
        home server, return a list of PDUs that were sent to that destination
        after it.

        Args:
            txn
            transaction_id (str)
            destination (str)
            local_server (str)

        Returns
            list: A list of PduTuple
        """
        return cls._get_pdus_after_transaction(
            txn, transaction_id, destination, local_server)

    @classmethod
    def paginate(cls, txn, context, pdu_list, limit):
        """Get a list of Pdus for a given topic that occured before (and
        including) the pdus in pdu_list. Return a list of max size `limit`.

        Args:
            txn
            context (str)
            pdu_list (list)
            limit (int)

        Return:
            list: A list of PduTuples
        """
        return cls._paginate_interaction(txn, context, pdu_list, limit)

    @classmethod
    def is_new(cls, txn, pdu_id, origin, context, depth):
        """For a given Pdu, try and figure out if it's 'new', i.e., if it's
        not something we got randomly from the past, for example when we
        request the current state of the room that will probably return a bunch
        of pdus from before we joined.

        Args:
            txn
            pdu_id (str)
            origin (str)
            context (str)
            depth (int)

        Returns:
            bool
        """
        return cls._is_new_interaction(txn, pdu_id, origin, context, depth)

    @classmethod
    def update_min_depth(cls, txn, context, depth):
        """Update the minimum `depth` of the given context, which is the line
        where we stop paginating backwards on.

        Args:
            txn
            context (str)
            depth (int)
        """
        return cls._update_min_depth_interaction(txn, context, depth)

    @classmethod
    def get_min_depth(cls, txn, context):
        """Get the current minimum depth for a context

        Args:
            txn
            context (str)
        """
        return cls._get_min_depth_interaction(txn, context)

    @classmethod
    def get_back_extremities(cls, txn, context):
        """Get a list of Pdus that we paginated beyond yet (and haven't seen).
        This list is used when we want to paginate backwards and is the list we
        send to the remote server.

        Args:
            txn
            context (str)

        Returns:
            list: A list of PduIdTuple.
        """
        return cls._get_back_extremities_interaction(txn, context)

    @classmethod
    def _get_pdu_interaction(cls, txn, pdu_id, origin):
        query = PdusTable.select_statement("pdu_id = ? AND origin = ?")
        txn.execute(query, (pdu_id, origin))

        results = PdusTable.decode_results(txn.fetchall())

        logger.debug(
            "_get_pdu_interaction: pdu_id=%s, origin=%s results: %s",
            pdu_id, origin, repr(results))

        if len(results) == 1:
            pdu_entry = results[0]
        else:
            return None

        return cls._get_pdu_tuple_from_entry(txn, pdu_entry)

    @classmethod
    def _get_current_state_interaction(cls, txn, context):
        query = (
            "SELECT %(fields)s FROM %(pdus)s as p "
            "INNER JOIN %(curr)s as c ON "
            "c.pdu_id = p.pdu_id AND "
            "c.origin = p.origin "
            "WHERE c.context = ?"
        ) % {
            "fields": PdusTable.get_fields_string(prefix="p"),
            "pdus": PdusTable.table_name,
            "curr": CurrentStateTable.table_name,
        }

        txn.execute(query, (context,))

        pdus = PdusTable.decode_results(txn.fetchall())
        return cls._get_pdu_tuple_from_entries(txn, pdus)

    @classmethod
    def _insert_interaction(cls, txn, entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), entry)

        cls._handle_prev_pdus(
            txn, entry.outlier, entry.pdu_id, entry.origin,
            prev_pdus, entry.context
        )

    @classmethod
    def _insert_state_interaction(cls, txn, pdu_entry,
                                  state_entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), pdu_entry)
        txn.execute(StatePdusTable.insert_statement(), state_entry)

        cls._handle_prev_pdus(
            txn,
            pdu_entry.outlier, pdu_entry.pdu_id, pdu_entry.origin, prev_pdus,
            pdu_entry.context
        )

    @staticmethod
    def _mark_as_processed_interaction(txn, pdu_id, pdu_origin):
        txn.execute("UPDATE %s SET have_processed = 1" % PdusTable.table_name)

    @staticmethod
    def _handle_prev_pdus(txn, outlier, pdu_id, origin, prev_pdus,
                          context):
        txn.executemany(
            PduEdgesTable.insert_statement(),
            [(pdu_id, origin, p[0], p[1], context) for p in prev_pdus]
        )

        # Update the extremities table if this is not an outlier.
        if not outlier:

            # First, we delete the new one from the forwards extremities table.
            query = (
                "DELETE FROM %s WHERE pdu_id = ? AND origin = ?"
                % PduForwardExtremitiesTable.table_name
            )
            txn.executemany(query, prev_pdus)

            # We only insert as a forward extremety the new pdu if there are no
            # other pdus that reference it as a prev pdu
            query = (
                "INSERT INTO %(table)s (pdu_id, origin, context) "
                "SELECT ?, ?, ? WHERE NOT EXISTS ("
                "SELECT 1 FROM %(pdu_edges)s WHERE "
                "prev_pdu_id = ? AND prev_origin = ?"
                ")"
            ) % {
                "table": PduForwardExtremitiesTable.table_name,
                "pdu_edges": PduEdgesTable.table_name
            }

            logger.debug("query: %s", query)

            txn.execute(query, (pdu_id, origin, context, pdu_id, origin))

            # Insert all the prev_pdus as a backwards thing, they'll get
            # deleted in a second if they're incorrect anyway.
            txn.executemany(
                PduBackwardExtremitiesTable.insert_statement(),
                [(i, o, context) for i, o in prev_pdus]
            )

            # Also delete from the backwards extremities table all ones that
            # reference pdus that we have already seen
            query = (
                "DELETE FROM %(pdu_back)s WHERE EXISTS ("
                "SELECT 1 FROM %(pdus)s AS pdus "
                "WHERE "
                "%(pdu_back)s.pdu_id = pdus.pdu_id "
                "AND %(pdu_back)s.origin = pdus.origin "
                "AND not pdus.outlier "
                ")"
            ) % {
                "pdu_back": PduBackwardExtremitiesTable.table_name,
                "pdus": PdusTable.table_name,
            }
            txn.execute(query)

    @staticmethod
    def _get_prev_pdus_interaction(txn, context):
        query = (
            "SELECT p.pdu_id, p.origin, p.depth FROM %(pdus)s as p "
            "INNER JOIN %(forward)s as f ON p.pdu_id = f.pdu_id "
            "AND f.origin = p.origin "
            "WHERE f.context = ?"
        ) % {
            "pdus": PdusTable.table_name,
            "forward": PduForwardExtremitiesTable.table_name,
        }

        logger.debug("get_prev query: %s" % query)

        txn.execute(
            query,
            (context, )
        )

        results = txn.fetchall()

        return [(row[0], row[1], row[2]) for row in results]

    @classmethod
    def _get_pdus_after_transaction(cls, txn, transaction_id, destination,
                                    local_server):
        pdus_fields = ", ".join(["pdus.%s" % f for f in PdusTable.fields])

        # Query that first get's all transaction_ids with an id greater than
        # the one given from the `sent_transactions` table. Then JOIN on this
        # from the `tx->pdu` table to get a list of (pdu_id, origin) that
        # specify the pdus that were sent in those transactions.
        # Finally, JOIN that from the `pdus` table to get all the attributes of
        # those PDUs.
        query = (
            "SELECT %(fields)s FROM %(pdus)s INNER JOIN ("
            "SELECT pdu_id, pdu_origin FROM %(tx_pdu)s as tp "
            "INNER JOIN %(sent_tx)s as st "
            "ON tp.transaction_id = st.transaction_id "
            "AND tp.destination = st.destination "
            "WHERE st.id > ("
            "SELECT id FROM %(sent_tx)s "
            "WHERE transaction_id = ? AND destination = ?"
            ")"
            ") AS t ON t.pdu_id = pdus.pdu_id AND pdus.origin = t.pdu_origin;"
        ) % {
            "fields": pdus_fields,
            "pdus": PdusTables.table_name,
            "tx_pdu": TransactionsToPduTable.table_name,
            "sent_tx": SentTransactions.table_name,
        }

        txn.execute(query, (transaction_id, destination))

        pdus = PdusTable.decode_results(txn.fetchall())

        return cls._get_pdu_tuple_from_entries(txn, pdus)

    @classmethod
    def _get_pdu_tuple_from_entries(cls, txn, pdu_entries):
        return [cls._get_pdu_tuple_from_entry(txn, pdu) for pdu in pdu_entries]

    @staticmethod
    def _get_pdu_tuple_from_entry(txn, pdu_entry):
        txn.execute(
            PduEdgesTable.select_statement("pdu_id = ? AND origin = ?"),
            (pdu_entry.pdu_id, pdu_entry.origin)
        )

        edges = [
            (r.prev_pdu_id, r.prev_origin)
            for r in PduEdgesTable.decode_results(txn.fetchall())
        ]

        txn.execute(
            StatePdusTable.select_statement("pdu_id = ? AND origin = ?"),
            (pdu_entry.pdu_id, pdu_entry.origin)
        )

        states = StatePdusTable.decode_results(txn.fetchall())

        if states:
            state_entry = states[0]
        else:
            state_entry = None

        return PduTuple(pdu_entry, state_entry, edges)

    @classmethod
    def _paginate_interaction(cls, txn, context, pdu_list, limit):
        logger.debug(
            "_paginate_interaction: %s, %s, %s",
            context, repr(pdu_list), limit
        )

        pdu_results = []

        # We seed the pdu_results with the things from the pdu_list.
        for pdu_id, origin in pdu_list:
            query = PdusTable.select_statement("pdu_id = ? AND origin = ?")
            txn.execute(query, (pdu_id, origin))

            results = PdusTable.decode_results(txn.fetchall())

            if results:
                pdu_results.append(results[0])

        front = pdu_list

        pdu_fields = ", ".join(["p.%s" % f for f in PdusTable.fields])
        query = (
            "SELECT %(pdu_fields)s from %(pdu_table)s as p "
            "INNER JOIN %(edges_table)s as e ON "
            "p.pdu_id = e.prev_pdu_id "
            "AND p.origin = e.prev_origin "
            "AND p.context = e.context "
            "WHERE e.context = ? AND e.pdu_id = ? AND e.origin = ? "
            "LIMIT ?"
        ) % {
            "pdu_fields": pdu_fields,
            "pdu_table": PdusTable.table_name,
            "edges_table": PduEdgesTable.table_name,
        }

        # We iterate through all pdu_ids in `front` to select their previous
        # pdus. These are dumped in `new_front`. We continue until we reach the
        # limit *or* new_front is empty (i.e., we've run out of things to
        # select
        while front and len(pdu_results) < limit:

            new_front = []
            for pdu_id, origin in front:
                logger.debug(
                    "_paginate_interaction: i=%s, o=%s",
                    pdu_id, origin
                )

                txn.execute(
                    query,
                    (context, pdu_id, origin, limit - len(pdu_results))
                )

                entries = PdusTable.decode_results(txn.fetchall())

                for row in entries:
                    logger.debug(
                        "_paginate_interaction: got i=%s, o=%s",
                        row.pdu_id, row.origin
                    )
                    new_front.append((row.pdu_id, row.origin))
                    pdu_results.append(row)

            front = new_front

        # We also want to update the `prev_pdus` attributes before returning.
        return cls._get_pdu_tuple_from_entries(txn, pdu_results)

    @staticmethod
    def _is_new_interaction(txn, pdu_id, origin, context, depth):
        # If depth > min depth in back table, then we classify it as new.
        # OR if there is nothing in the back table, then it kinda needs to
        # be a new thing.
        query = (
            "SELECT min(p.depth) FROM %(edges)s as e "
            "INNER JOIN %(back)s as b "
            "ON e.prev_pdu_id = b.pdu_id AND e.prev_origin = b.origin "
            "INNER JOIN %(pdus)s as p "
            "ON e.pdu_id = p.pdu_id AND p.origin = e.origin "
            "WHERE p.context = ?"
        ) % {
            "pdus": PdusTable.table_name,
            "edges": PduEdgesTable.table_name,
            "back": PduBackwardExtremitiesTable.table_name,
        }

        txn.execute(query, (context,))

        min_depth, = txn.fetchone()

        if not min_depth or depth > int(min_depth):
            logger.debug(
                "is_new true: id=%s, o=%s, d=%s min_depth=%s",
                pdu_id, origin, depth, min_depth
            )
            return True

        # If this pdu is in the forwards table, then it also is a new one
        query = (
            "SELECT * FROM %(forward)s WHERE pdu_id = ? AND origin = ?"
        ) % {
            "forward": PduForwardExtremitiesTable.table_name,
        }

        txn.execute(query, (pdu_id, origin))

        # Did we get anything?
        if txn.fetchall():
            logger.debug(
                "is_new true: id=%s, o=%s, d=%s was forward",
                pdu_id, origin, depth
            )
            return True

        logger.debug(
            "is_new false: id=%s, o=%s, d=%s",
            pdu_id, origin, depth
        )

        # FINE THEN. It's probably old.
        return False

    @classmethod
    def _update_min_depth_interaction(cls, txn, context, depth):
        min_depth = cls._get_min_depth_interaction(txn, context)

        do_insert = depth < min_depth if min_depth else True

        if do_insert:
            txn.execute(
                "INSERT OR REPLACE INTO %s (context, min_depth) "
                "VALUES (?,?)" % ContextDepthTable.table_name,
                (context, depth)
            )

    @staticmethod
    def _get_min_depth_interaction(txn, context):
        txn.execute(
            "SELECT min_depth FROM %s WHERE context = ?"
            % ContextDepthTable.table_name,
            (context,)
        )

        row = txn.fetchone()

        return row[0] if row else None

    @staticmethod
    def _get_back_extremities_interaction(txn, context):
        txn.execute(
            "SELECT pdu_id, origin FROM %(back)s WHERE context = ?"
            % {"back": PduBackwardExtremitiesTable.table_name, },
            (context,)
        )

        return [PduIdTuple(i, o) for i, o in txn.fetchall()]


class StateQueries(object):
    """A collection of queries for handling state PDUs.

    All functions are executed synchrously. To run them in an asynchronous
    fashion use `run_interaction`
    """

    @classmethod
    def get_next_missing_pdu(cls, txn, new_pdu):
        """When we get a new state pdu we need to check whether we need to do
        any conflict resolution, if we do then we need to check if we need
        to go back and request some more state pdus that we haven't seen yet.

        Args:
            txn
            new_pdu

        Returns:
            PduIdTuple: A pdu that we are missing, or None if we have all the
                pdus required to do the conflict resolution.
        """
        return cls._get_next_missing_pdu_interaction(txn, new_pdu)

    @classmethod
    def handle_new_state(cls, txn, new_pdu):
        """Actually perform conflict resolution on the new_pdu on the
        assumption we have all the pdus required to perform it.

        Args:
            txn
            new_pdu

        Returns:
            bool: True if the new_pdu clobbered the current state, False if not
        """
        return cls._handle_new_state_interaction(txn, new_pdu)

    @classmethod
    def current_state(cls, txn, context, pdu_type, state_key):
        """For a given context, pdu_type, state_key 3-tuple, return what is
        currently considered the current state.

        Args:
            txn
            context (str)
            pdu_type (str)
            state_key (str)

        Returns:
            PduAndStateTuple
        """
        return cls._get_current_interaction(txn, context, pdu_type, state_key)

    @classmethod
    def _get_next_missing_pdu_interaction(cls, txn, new_pdu):
        logger.debug(
            "_get_next_missing_pdu_interaction %s %s",
            new_pdu.pdu_id, new_pdu.origin
        )

        current = cls._get_current_interaction(
            txn,
            new_pdu.context, new_pdu.pdu_type, new_pdu.state_key
        )

        if (not current or not current.prev_state_id
                or not current.prev_state_origin):
            return None

        # Oh look, it's a straight clobber, so wooooo almost no-op.
        if (new_pdu.prev_state_id == current.pdu_id
                and new_pdu.prev_state_origin == current.origin):
            return None

        enum_branches = cls._enumerate_state_branches(txn, new_pdu, current)
        for branch, prev_state, state in enum_branches:
            if not state:
                return PduIdTuple(
                    prev_state.prev_state_id,
                    prev_state.prev_state_origin
                )

        return None

    @classmethod
    def _enumerate_state_branches(cls, txn, pdu_a, pdu_b):
        branch_a = pdu_a
        branch_b = pdu_b

        depth_a = pdu_a.depth
        depth_b = pdu_b.depth

        get_query = (
            "SELECT p.depth, %(fields)s FROM %(state)s as s "
            "INNER JOIN %(pdus)s as p "
            "ON p.pdu_id = s.pdu_id AND p.origin = s.origin "
            "WHERE s.pdu_id = ? AND s.origin = ? "
        ) % {
            "fields": StatePdusTable.get_fields_string(prefix="s"),
            "state": StatePdusTable.table_name,
            "pdus": PdusTable.table_name,
        }

        while True:
            if (branch_a.pdu_id == branch_b.pdu_id
                    and branch_a.origin == branch_b.origin):
                # Woo! We found a common ancestor
                break

            if int(depth_a) < int(depth_b):
                pdu_tuple = PduIdTuple(
                    branch_a.prev_state_id,
                    branch_a.prev_state_origin
                )

                txn.execute(get_query, pdu_tuple)

                res = txn.fetchall()
                states = StatePdusTable.decode_results(
                    res[1:]
                )

                prev_branch = branch_a
                branch_a = states[0] if states else None

                yield (0, prev_branch, branch_a)

                if not branch_a:
                    break
                else:
                    depth_a = res[0]
            else:
                pdu_tuple = PduIdTuple(
                    branch_b.prev_state_id,
                    branch_b.prev_state_origin
                )
                txn.execute(get_query, pdu_tuple)

                res = txn.fetchall()
                states = StatePdusTable.decode_results(
                    res[1:]
                )

                prev_branch = branch_b
                branch_b = states[0] if states else None

                yield (1, prev_branch, branch_b)

                if not states:
                    break
                else:
                    depth_b = res[0]

    @classmethod
    def _handle_new_state_interaction(cls, txn, new_pdu):
        logger.debug(
            "_handle_new_state_interaction %s %s",
            new_pdu.pdu_id, new_pdu.origin
        )

        current = cls._get_current_interaction(
            txn,
            new_pdu.context, new_pdu.pdu_type, new_pdu.state_key
        )

        is_current = False

        if (not current or not current.prev_state_id
                or not current.prev_state_origin):
            # Oh, we don't have any state for this yet.
            is_current = True
        elif (current.pdu_id == new_pdu.prev_state_id
                and current.origin == new_pdu.prev_state_origin):
            # Oh! A direct clobber. Just do it.
            is_current = True
        else:
            ##
            # Ok, now loop through until we get to a common ancestor.
            max_new = int(new_pdu.power_level)
            max_current = int(current.power_level)

            enum_branches = cls._enumerate_state_branches(
                txn, new_pdu, current
            )
            for branch, prev_state, state in enum_branches:
                if not state:
                    raise RuntimeError(
                        "Could not find state_pdu %s %s" %
                        (
                            prev_state.prev_state_id,
                            prev_state.prev_state_origin
                        )
                    )

                if branch == 0:
                    max_new = max(int(state.depth), max_new)
                else:
                    max_current = max(int(state.depth), max_current)

            is_current = max_new > max_current

        if is_current:
            logger.debug("_handle_new_state_interaction make current")

            # Right, this is a new thing, so woo, just insert it.
            txn.execute(
                "INSERT OR REPLACE INTO %(curr)s (%(fields)s) VALUES (%(qs)s)"
                % {
                    "curr": CurrentStateTable.table_name,
                    "fields": CurrentStateTable.get_fields_string(),
                    "qs": ", ".join(["?"] * len(CurrentStateTable.fields))
                },
                CurrentStateTable.EntryType(
                    *(new_pdu.__dict__[k] for k in CurrentStateTable.fields)
                )
            )
        else:
            logger.debug("_handle_new_state_interaction not current")

        logger.debug("_handle_new_state_interaction done")

        return is_current

    @staticmethod
    def _get_current_interaction(txn, context, pdu_type, state_key):
        logger.debug(
            "_get_current_interaction %s %s %s",
            context, pdu_type, state_key
        )

        fields = [
            "p.%s" % r if r in PdusTable.fields else "s.%s" % r
            for r in pdu_state_fields
        ]

        current_query = (
            "SELECT %(fields)s FROM %(state)s as s "
            "INNER JOIN %(pdus)s as p "
            "ON s.pdu_id = p.pdu_id AND s.origin = p.origin "
            "INNER JOIN %(curr)s as c "
            "ON s.pdu_id = c.pdu_id AND s.origin = c.origin "
            "WHERE s.context = ? AND s.pdu_type = ? AND s.state_key = ? "
        ) % {
            "fields": ", ".join(fields),
            "curr": CurrentStateTable.table_name,
            "state": StatePdusTable.table_name,
            "pdus": PdusTable.table_name,
        }

        txn.execute(
            current_query,
            (context, pdu_type, state_key)
        )

        rows = txn.fetchall()

        if not rows:
            logger.debug("_get_current_interaction not found")
            return None

        # We should only ever get 0 or 1 due to table restraints
        current = PduAndStateTuple(*(rows[0]))

        logger.debug(
            "_get_current_interaction found %s %s",
            current.pdu_id, current.origin
        )
        return current
