# -*- coding: utf-8 -*-


from twisted.internet import defer

from synapse.persistence.transactions import (
    TransactionQueries, PduQueries,
    StateQueries, run_interaction
)

from synapse.persistence.tables import ReceivedTransactionsTable

from .units import Pdu

import copy
import json
import logging


logger = logging.getLogger(__name__)


class PduActions(object):
    @staticmethod
    @defer.inlineCallbacks
    def current_state(context):
        results = yield run_interaction(
            PduQueries.get_current_state,
            context
        )

        defer.returnValue([Pdu.from_pdu_tuple(p) for p in results])

    @staticmethod
    @defer.inlineCallbacks
    def get_persisted_pdu(pdu_id, pdu_origin):
        pdu_tuple = yield run_interaction(
            PduQueries.get_pdu,
            pdu_id, pdu_origin
        )

        defer.returnValue(Pdu.from_pdu_tuple(pdu_tuple))

    @classmethod
    def persist_received(cls, pdu):
        return cls._persist(pdu)

    @classmethod
    @defer.inlineCallbacks
    def persist_outgoing(cls, pdu):
        ret = yield cls._persist(pdu)

        # This is safe to do since if *we* are sending something, then we must
        # have seen everything we reference (hopefully).
        if pdu.is_state:
            yield run_interaction(
                StateQueries.handle_new_state,
                pdu
            )

        defer.returnValue(ret)

    @classmethod
    @defer.inlineCallbacks
    def _persist(cls, pdu):
        kwargs = copy.copy(pdu.__dict__)
        del kwargs["content"]
        kwargs["content_json"] = json.dumps(pdu.content)
        kwargs["unrecognized_keys"] = json.dumps(kwargs["unrecognized_keys"])

        logger.debug("Persisting: %s", repr(kwargs))

        if pdu.is_state:
            ret = yield run_interaction(
                PduQueries.insert_state,
                **kwargs
            )
        else:
            ret = yield run_interaction(
                PduQueries.insert,
                **kwargs
            )

        yield run_interaction(
            PduQueries.update_min_depth,
            pdu.context, pdu.depth
        )

        defer.returnValue(ret)

    @staticmethod
    def mark_as_processed(pdu):
        return run_interaction(
            PduQueries.mark_as_processed,
            pdu.pdu_id, pdu.origin
        )

    @classmethod
    @defer.inlineCallbacks
    def populate_previous_pdus(cls, pdu):
        results = yield run_interaction(
            PduQueries.get_prev_pdus,
            pdu.context
        )

        pdu.prev_pdus = [(p_id, origin) for p_id, origin, _ in results]

        vs = [int(v) for _, _, v in results]
        if vs:
            pdu.depth = max(vs) + 1
        else:
            pdu.depth = 0

        if pdu.is_state:
            curr = yield run_interaction(
                StateQueries.current_state,
                pdu.context,
                pdu.pdu_type, pdu.state_key)

            if curr:
                pdu.prev_state_id = curr.pdu_id
                pdu.prev_state_origin = curr.origin
            else:
                pdu.prev_state_id = None
                pdu.prev_state_origin = None

    @staticmethod
    @defer.inlineCallbacks
    def after_transaction(transaction_id, destination, origin):
        results = yield run_interaction(
            PduQueries.get_after_transaction,
            transaction_id,
            destination,
            origin
        )

        defer.returnValue([Pdu.from_pdu_tuple(p) for p in results])

    @staticmethod
    @defer.inlineCallbacks
    def paginate(context, pdu_list, limit):
        results = yield run_interaction(
            PduQueries.paginate,
            context, pdu_list, limit
        )

        defer.returnValue([Pdu.from_pdu_tuple(p) for p in results])

    @staticmethod
    def is_new(pdu):
        return run_interaction(
            PduQueries.is_new,
            pdu_id=pdu.pdu_id,
            origin=pdu.origin,
            context=pdu.context,
            depth=pdu.depth
        )


class TransactionActions(object):
    @staticmethod
    def have_responded(transaction):
        if not transaction.transaction_id:
            raise RuntimeError("Cannot persist a transaction with no "
                               "transaction_id")

        return run_interaction(
            TransactionQueries.get_response_for_received,
            transaction.transaction_id, transaction.origin
        )

    @staticmethod
    def set_response(transaction, code, response):
        if not transaction.transaction_id:
            raise RuntimeError("Cannot persist a transaction with no "
                               "transaction_id")

        return run_interaction(
            TransactionQueries.set_recieved_txn_response,
            transaction.transaction_id,
            transaction.origin,
            code,
            json.dumps(response)
        )

    @staticmethod
    def persist_as_received(transaction, response_code, response_json):
        return run_interaction(
            TransactionQueries.insert_received,
            ReceivedTransactionsTable.EntryType(
                transaction_id=transaction.transaction_id,
                origin=transaction.origin,
                ts=transaction.ts,
                response_code=response_code,
                response_json=json.dumps(response_json)
            ),
            transaction.previous_ids
        )

    @staticmethod
    @defer.inlineCallbacks
    def prepare_to_send(transaction):
        transaction.prev_ids = yield run_interaction(
            TransactionQueries.prep_send_transaction,
            transaction.transaction_id,
            transaction.destination,
            transaction.ts,
            [(p["pdu_id"], p["origin"]) for p in transaction.pdus]
        )

    @staticmethod
    def delivered(transaction, response_code, response_json):
        return run_interaction(
            TransactionQueries.delivered_txn,
            transaction.transaction_id,
            transaction.destination,
            response_code,
            json.dumps(response_json)
        )