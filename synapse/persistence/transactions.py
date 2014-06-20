# -*- coding: utf-8 -*-

from tables import (ReceivedTransactionsTable, SentTransactions,
    TransactionsToPduTable, PdusTable, StatePdusTable, PduEdgesTable,
    PduForwardExtremetiesTable)
from .. import utils

from twisted.internet import defer

from collections import namedtuple

import logging

#dbpool = None  # XXX: We need to do something.

logger = logging.getLogger("synapse.persistence.transactions")

PduTuple = namedtuple("PduTuple", ("pdu_entry", "prev_pdu_list"))
TransactionTuple = namedtuple("TransactionTuple", ("tx_entry", "prev_ids"))


class TransactionQueries(object):

    @classmethod
    @defer.inlineCallbacks
    def get_response_for_received(clz, transaction_id, origin):
        result = yield utils.get_db_pool().runInteraction(
            clz._get_received_interaction,
            transaction_id, origin)

        if result and result.response_code:
            defer.returnValue(
                    (result.response_code, result.response_json)
                )
        else:
            defer.returnValue(None)

    @classmethod
    def insert_received(clz, tx_tuple):
        #entry = ReceivedTransactionsTable.EntryType(**pdu_tuple.entry)
        return utils.DBPOOL.runInteraction(clz._insert_interaction, tx_tuple)

    @classmethod
    def set_recieved_txn_response(clz, transaction_id, origin, code,
    response_json):
        return utils.get_db_pool().runInteraction(
            clz._set_recieved_response_interaction,
            transaction_id, origin, code, response_json)

    @classmethod
    def prep_send_transaction(clz, transaction_id, destination, ts,
    pdu_list):
        return utils.get_db_pool().runInteraction(
            clz._prep_send_transaction_interaction,
            transaction_id, destination, ts, pdu_list)

    @classmethod
    def delivered_txn(clz, transaction_id, destination,
    code, response_json):
        return utils.get_db_pool().runInteraction(
            clz._delivered_txn_interaction,
            transaction_id, destination, code, response_json)

    @classmethod
    def get_transactions_after(clz, transaction_id, destination):
        return utils.get_db_pool().runInteraction(
            clz._get_transactions_after_interaction,
            transaction_id, destination)

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
        query = ("UPDATE %s "
            "SET response_code = ?, response_json = ? "
            "WHERE transaction_id = ? AND origin = ?"
            ) % ReceivedTransactionsTable.table_name

        txn.execute(query, (code, response_json, transaction_id, origin))

    @staticmethod
    def _delivered_txn_interaction(txn, transaction_id, destination,
    code, response_json):
        # Say what response we got.
        query = ("UPDATE %s "
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
    def _get_transactions_after_interaction(clz, txn, transaction_id,
    destination):
        where = ("destination = ? AND id > (select id FROM %s WHERE "
            "transaction_id = ? AND destination = ?)") % (
                SentTransactions.table_name
            )
        query = SentTransactions.select_statement(where)

        txn.execute(query, (destination, transaction_id, destination))

        return ReceivedTransactionsTable.decode_results(txn.fetchall())


class PduQueries(object):

    @classmethod
    def get_pdu(clz, pdu_id, origin):
        return utils.get_db_pool().runInteraction(clz._get_pdu_interaction,
             pdu_id, origin)

    @classmethod
    def get_current_state(clz, context):
        return utils.get_db_pool().runInteraction(
            clz._get_current_state_interaction,
            context)

    @classmethod
    def insert(clz, prev_pdus, **cols):
        entry = PdusTable.EntryType(
                **{k: cols.get(k, None) for k in PdusTable.fields}
            )
        return utils.get_db_pool().runInteraction(
            clz._insert_interaction,
            entry, prev_pdus)

    @classmethod
    def insert_state(clz, prev_pdus, **cols):
        pdu_entry = PdusTable.EntryType(
                **{k: cols[k] for k in PdusTable.fields}
            )
        state_entry = StatePdusTable.EntryType(
                **{k: cols[k] for k in StatePdusTable.fields}
            )
        return utils.get_db_pool().runInteraction(
            clz._insert_state_interaction,
            pdu_entry, state_entry, prev_pdus)

    @classmethod
    def get_prev_pdus(clz, context):
        return utils.get_db_pool().runInteraction(
            clz._get_prev_pdus_interaction,
            context)

    @classmethod
    def get_after_transaction(clz, transaction_id, destination, local_server):
        return utils.get_db_pool().runInteraction(
            clz._get_pdus_after_transaction,
            transaction_id, destination, local_server)

    @staticmethod
    def _get_pdu_interaction(txn, pdu_id, origin):
        query = PdusTable.select_statement("pdu_id = ? AND origin = ?")
        txn.execute(query, (pdu_id, origin))

        results = PdusTable.decode_results(txn.fetchall())

        if len(results) == 1:
            pdu_entry = results[0]
        else:
            return None

        txn.execute(
            PduEdgesTable.select_statement("pdu_id = ? AND origin = ?"),
            (pdu_entry.pdu_id, pdu_entry.origin)
        )

        edges = [(r.prev_pdu_id, r.prev_origin)
            for r in PduEdgesTable.decode_results(txn.fetchall())]

        return PduTuple(pdu_entry, edges)

    @classmethod
    def _get_current_state_interaction(clz, txn, context):
        pdus_fields = ", ".join(["pdus.%s" % f for f in PdusTable.fields])

        query = ("SELECT %s FROM pdus INNER JOIN state_pdus ON "
                "state_pdus.pdu_id = pdus.pdu_id AND "
                "state_pdus.origin = pdus.origin "
                "WHERE state_pdus.context = ?") % pdus_fields

        txn.execute(query, (context,))

        pdus = PdusTable.decode_results(txn.fetchall())
        return clz._get_pdu_tuple_from_entries(txn, pdus)

    @classmethod
    def _insert_interaction(clz, txn, entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), entry)

        clz._handle_prev_pdus(txn, entry.pdu_id, entry.origin, prev_pdus,
            entry.context)

    @classmethod
    def _insert_state_interaction(clz, txn, pdu_entry, state_entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), pdu_entry)
        txn.execute(StatePdusTable.insert_statement(), state_entry)

        clz._handle_prev_pdus(txn,
             pdu_entry.pdu_id, pdu_entry.origin, prev_pdus, pdu_entry.context)

    @staticmethod
    def _handle_prev_pdus(txn, pdu_id, origin, prev_pdus, context):
        txn.executemany(PduEdgesTable.insert_statement(),
                [(pdu_id, origin, p[0], p[1]) for p in prev_pdus]
            )

        ## Update the extremeties table

        # First, we delete any from the forwards extremeties table.
        query = ("DELETE FROM %s WHERE pdu_id = ? AND origin = ?" %
            PduForwardExtremetiesTable.table_name)
        txn.executemany(query, prev_pdus)

        # We only insert the new pdu if there are no other pdus that reference
        # it as a prev pdu
        query = (
            "INSERT INTO %(table)s (pdu_id, origin, context) "
            "SELECT ?, ?, ? WHERE NOT EXISTS ("
                "SELECT 1 FROM %(pdu_edges)s WHERE "
                "prev_pdu_id = ? AND prev_origin = ?"
            ")"
            ) % {
                "table": PduForwardExtremetiesTable.table_name,
                "pdu_edges": PduEdgesTable.table_name
            }

        logger.debug("query: %s", query)

        txn.execute(query, (pdu_id, origin, context, pdu_id, origin))

    @staticmethod
    def _get_prev_pdus_interaction(txn, context):
        txn.execute(
            PduForwardExtremetiesTable.select_statement("context = ?"),
            (context, )
        )

        results = PduForwardExtremetiesTable.decode_results(txn.fetchall())

        return [(row.pdu_id, row.origin) for row in results]

    @classmethod
    def _get_pdus_after_transaction(clz, txn, transaction_id, destination,
    local_server):
        pdus_fields = ", ".join(["pdus.%s" % f for f in PdusTable.fields])

        # Query that first get's all transaction_ids with an id greater than
        # the one given from the `sent_transactions` table. Then JOIN on this
        # from the `tx->pdu` table to get a list of (pdu_id, origin) that
        # specify the pdus that were sent in those transactions.
        # Finally, JOIN that from the `pdus` table to get all the attributes of
        # those PDUs.
        query = (
            "SELECT %(fields)s FROM pdus INNER JOIN ("
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
            "tx_pdu": TransactionsToPduTable.table_name,
            "sent_tx": SentTransactions.table_name,
        }

        txn.execute(query, (transaction_id, destination))

        pdus = PdusTable.decode_results(txn.fetchall())

        return clz._get_pdu_tuple_from_entries(txn, pdus)

    @staticmethod
    def _get_pdu_tuple_from_entries(txn, pdu_entries):
        results = []
        for pdu in pdu_entries:
            txn.execute(
                PduEdgesTable.select_statement("pdu_id = ? AND origin = ?"),
                (pdu.pdu_id, pdu.origin)
            )

            edges = [(r.prev_pdu_id, r.prev_origin)
                for r in PduEdgesTable.decode_results(txn.fetchall())]

            results.append(PduTuple(pdu, edges))

        return results
