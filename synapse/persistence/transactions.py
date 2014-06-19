# -*- coding: utf-8 -*-

from tables import (ReceivedTransactionsTable, SentTransactions,
    TransactionsToPduTable, PdusTable, StatePdusTable, PduEdgesTable,
    PduForwardExtremetiesTable)

from twisted.internet import defer

from ..utils import DBPOOL

from collections import namedtuple

#dbpool = None  # XXX: We need to do something.


PduTuple = namedtuple("PduTuple", ("pdu_entry", "prev_pdu_list"))
TransactionTuple = namedtuple("TransactionTuple", ("tx_entry", "prev_ids"))


class TransactionQueries(object):

    @classmethod
    @defer.inlineCallbacks
    def get_response_for_received(clz, transaction_id, origin):
        result = yield clz.get(transaction_id, origin)

        if result and result.response_code:
            defer.returnValue(
                    (result.response_code, result.response_json)
                )
        else:
            defer.returnValue(None)

    @classmethod
    def insert_received(clz, tx_tuple):
        #entry = ReceivedTransactionsTable.EntryType(**pdu_tuple.entry)
        return DBPOOL.run_interaction(clz._insert_interaction, tx_tuple)

    @classmethod
    def set_recieved_txn_response(clz, transaction_id, origin, code,
    response_json):
        return DBPOOL.run_interaction(clz._set_recieved_response_interaction,
            transaction_id, origin, code, response_json)

    @classmethod
    def prep_send_transaction(clz, transaction_id, destination, ts,
    pdu_id_list):
        return DBPOOL.run_interaction(clz._prep_send_transaction_interaction,
            transaction_id, destination, ts, pdu_id_list)

    @classmethod
    def delivered_txn(clz, transaction_id, destination,
    code, response_json):
        return DBPOOL.run_interaction(clz._delivered_txn_interaction,
            transaction_id, destination, code, response_json)

    @classmethod
    def get_transactions_after(clz, transaction_id, destination):
        return DBPOOL.run_interaction(clz._get_transactions_after_interaction,
            transaction_id, destination)

    @staticmethod
    def _get_sent_interaction(txn, transaction_id, destination):
        where_clause = "transaction_id = ? AND destination = ?"
        query = SentTransactions.select_statement(where_clause)

        txn.execute(query, transaction_id)

        results = SentTransactions.decode_results(txn.fetchall())

        if len(results) == 0:
            return None
        else:
            return results[1]

    @staticmethod
    def _get_received_interaction(txn, transaction_id, origin):
        where_clause = "transaction_id = ? AND origin = ?"
        query = ReceivedTransactionsTable.select_statement(where_clause)

        txn.execute(query, transaction_id)

        results = ReceivedTransactionsTable.decode_results(txn.fetchall())

        if len(results) == 0:
            return None
        else:
            return results[1]

    @staticmethod
    def _insert_received_interaction(txn, tx_tuple):
        query = ReceivedTransactionsTable.insert_statement()

        txn.execute(query, *tx_tuple.tx_entry)

        query = (
                "UPDATE %s SET has_been_referenced = 1 "
                "WHERE transaction_id = ? AND orign = ?"
                ) % ReceivedTransactionsTable.table_name

        origin = tx_tuple.tx_entry.origin

        txn.executemany(query, [
                (tx_id, origin) for tx_id in tx_tuple.prev_ids
            ])

        txn.commit()

    @staticmethod
    def _set_recieved_txn_response_interaction(txn, transaction_id, origin,
    code, response_json):
        query = ("UPDATE %s "
            "SET response_code = ?, response_json = ? "
            "WHERE transaction_id = ? AND origin = ?"
            ) % ReceivedTransactionsTable.table_name

        txn.execute(query, code, response_json, transaction_id, origin)

        txn.commit()

    @staticmethod
    def _delivered_txn_interaction(txn, transaction_id, destination,
    code, response_json):
        # Say what response we got.
        query = ("UPDATE %s "
            "SET response_code = ?, response_json = ? "
            "WHERE transaction_id = ? AND origin = ?"
            ) % SentTransactions.table_name

        txn.execute(query, code, response_json, transaction_id, destination)

        txn.commit()

    @staticmethod
    def _prep_send_transaction_interaction(txn, transaction_id, destination,
    ts, pdu_id_list):
        # First we find out what the prev_txs should be.
        # Since we know that we are only sending one transaction at a time,
        # we can simply take the last one.
        query = "%s ORDER BY %s DESC LIMIT 1" % (
                SentTransactions.select_statement(),
                "id"
            )

        results = txn.execute(query, destination)
        results = SentTransactions.decode_results(results)

        prev_txns = [r.transaction_id for r in results]

        # Actually add the new transaction to the sent_transactions table.

        query = SentTransactions.insert_statement()
        txn.execute(query, SentTransactions.EntryType(
                transaction_id=transaction_id,
                destination=destination,
                ts=ts,
                response_code=0,
                response_json=None,
                have_referenced=0
            ))

        # Update the tx id -> pdu id mapping

        query = TransactionsToPduTable.insert_statement()
        txn.executemany(query, [
                (transaction_id, destination, pdu_id)
                for pdu_id in pdu_id_list
            ])

        # Commit!

        txn.commit()

        return prev_txns

    @classmethod
    def _get_transactions_after_interaction(clz, txn, transaction_id,
    destination):
        where = ("destination = ? AND id > (select id FROM %s WHERE "
            "transaction_id = ? AND destination = ?)") % (
                SentTransactions.table_name
            )
        query = SentTransactions.select_statement(where)

        txn.execute(query, destination, transaction_id, destination)

        return ReceivedTransactionsTable.decode_results(txn.fetchall())


class PduQueries(object):

    @classmethod
    def get_pdu(clz, pdu_id, origin):
        return DBPOOL.run_interaction(clz._get_pdu_interaction,
             pdu_id, origin)

    @classmethod
    def get_current_state(clz, context):
        return DBPOOL.run_interaction(clz._get_current_state_interaction,
            context)

    @classmethod
    def insert(clz, prev_pdus, **cols):
        entry = PdusTable.EntryType(**cols)
        return DBPOOL.run_interaction(clz._insert_interaction,
            entry, prev_pdus)

    @classmethod
    def insert_state(clz, prev_pdus, **cols):
        pdu_entry = PdusTable.EntryType(
                [cols[k] for k in PdusTable.fields]
            )
        state_entry = StatePdusTable.EntryType(
                [cols[k] for k in StatePdusTable.fields]
            )
        return DBPOOL.run_interaction(clz._insert_received_interaction,
            pdu_entry, state_entry, prev_pdus)

    @classmethod
    def get_prev_pdus(clz, context):
        return DBPOOL.run_interaction(clz._get_prev_pdus_interaction,
            context)

    @classmethod
    def get_after_transaction(clz, transaction_id, destination, local_server):
        return DBPOOL.run_interaction(clz._get_pdus_after_transaction,
            transaction_id, destination, local_server)

    @staticmethod
    def _get_pdu_interaction(txn, pdu_id, origin):
        query = PdusTable.select_statement("pdu_id = ? AND origin = ?")
        txn.execute(query, pdu_id, origin)

        results = PdusTable.decode_results(txn.fetchall())

        if len(results) == 1:
            pdu_entry = results[0]
        else:
            return None

        txn.execute(
            PduEdgesTable.select_statement("pdu_id = ? AND origin = ?"),
            pdu_entry.pdu_id, pdu_entry.origin
        )

        edges = [(r.prev_pdu_id, r.prev_origin)
            for r in PduEdgesTable.decode_results(txn.fetchall())]

        return PduTuple(pdu_entry, edges)

    @staticmethod
    def _get_current_state_interaction(txn, context):
        pdus_fields = ", ".join(["pdus.%s" % f for f in PdusTable.fields])

        query = ("SELECT %s FROM pdus INNER JOIN state_pdu ON "
                "state_pdus.pdu_id = pdus.pdu_id AND "
                "state_pdus.origin = pdus.origin"
                "WHERE state_pdu.context = ?") % pdus_fields

        txn.execute(query, context)

        return PdusTable.decode_results(txn.fetchall())

    @classmethod
    def _insert_interaction(clz, txn, entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), *entry)

        clz._handle_prev_pdus(txn, entry.pdu_id, entry.origin, prev_pdus)

        txn.commit()

    @classmethod
    def _insert_state_interaction(clz, txn, pdu_entry, state_entry, prev_pdus):
        txn.execute(PdusTable.insert_statement(), *pdu_entry)
        txn.execute(StatePdusTable.insert_statement(), *state_entry)

        clz._handle_prev_pdus(txn,
             pdu_entry.pdu_id, pdu_entry.origin, prev_pdus)

        txn.commit()

    @staticmethod
    def _handle_prev_pdus(clx, txn, pdu_id, origin, prev_pdus):
        txn.executemany(PduEdgesTable.insert_statement(),
                [(pdu_id, origin, p[0], p[1]) for p in prev_pdus]
            )

        ## Update the extremeties table

        # First, we delete any from the forwards extremeties table.
        query = ("DELETE FROM %s WHERE pdu_id = ? AND origin = ?" %
            PduForwardExtremetiesTable.table_name)
        txn.executemany(query, prev_pdus)

        # Second....

    @staticmethod
    def _get_prev_pdus_interaction(txn, context):
        txn.execute(
            PduForwardExtremetiesTable.select_statement("context = ?"),
            context
        )

        results = PduForwardExtremetiesTable.decode_results(txn.fetchall())

        return [(row.pdu_id, row.origin) for row in results]

    @staticmethod
    def _get_pdus_after_transaction(txn, transaction_id, destination,
    local_server):
        pdus_fields = ", ".join(["pdus.%s" % f for f in PdusTable.fields])

        # Subquery to get all transactions that we've sent after the given
        where = ("destination = ? AND id > (select id FROM %s WHERE "
            "transaction_id = ? AND destination = ?)") % (
                SentTransactions.table_name
            )
        subquery = SentTransactions.select_statement(where)

        # Get the attributes of PDUs in the subquery
        query = ("SELECT %s FROM pdus INNER JOIN (%s) as t ON "
            "pdus.id = t.pdu_id AND pdus.origin = ?") % (pdus_fields, subquery)

        txn.execute(query, transaction_id, destination, local_server)

        pdus = PdusTable.decode_results(txn.fetchall())

        # Now get all the "previous_pdus" versioning gunk.
        results = []
        for pdu in pdus:
            txn.execute(
                PduEdgesTable.select_statement("pdu_id = ? AND origin = ?"),
                pdu.pdu_id, pdu.origin
            )

            edges = [(r.prev_pdu_id, r.prev_origin)
                for r in PduEdgesTable.decode_results(txn.fetchall())]

            results.append(PduTuple(pdu, edges))

        return results
