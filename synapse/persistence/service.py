# -*- coding: utf-8 -*-
""" We funnel all persistence queries through a single interface to make it
easier to mock or swap to a different persistence service.
"""


from .transactions import (
    TransactionQueries, PduQueries, StateQueries
)


class PersistenceService(object):

    def __init__(self, hs):
        self._db_pool = hs.get_db_pool()

    def get_received_txn_response(self, transaction_id, origin):
        return self._db_pool.runInteraction(
            TransactionQueries.get_response_for_received,
            transaction_id, origin
        )

    def set_received_txn_response(self, transaction_id, origin, code,
                                  response_dict):
        return self._db_pool.runInteraction(
            TransactionQueries.set_received_txn_response,
            transaction_id, origin, code, response_dict
        )

    def prep_send_transaction(self, transaction_id, destination, ts, pdu_list):
        return self._db_pool.runInteraction(
            TransactionQueries.prep_send_transaction,
            transaction_id, destination, ts, pdu_list
        )

    def delivered_txn(self, transaction_id, destination, code, response_dict):
        return self._db_pool.runInteraction(
            TransactionQueries.delivered_txn,
            transaction_id, destination, code, response_dict
        )

    def get_transactions_after(self, transaction_id, destination):
        return self._db_pool.runInteraction(
            TransactionQueries.get_transactions_after,
            transaction_id, destination
        )

    def get_pdu(self, pdu_id, origin):
        return self._db_pool.runInteraction(
            PduQueries.get_pdu,
            pdu_id, origin
        )

    def get_current_state_for_context(self, context):
        return self._db_pool.runInteraction(
            PduQueries.get_current_state,
            context
        )

    def persist_pdu(self, prev_pdus, **cols):
        return self._db_pool.runInteraction(
            PduQueries.insert,
            prev_pdus, **cols
        )

    def persist_state(self, prev_pdus, **cols):
        return self._db_pool.runInteraction(
            PduQueries.insert_state,
            prev_pdus, **cols
        )

    def mark_pdu_as_processed(self, pdu_id, pdu_origin):
        return self._db_pool.runInteraction(
            PduQueries.mark_as_processed,
            pdu_id, pdu_origin
        )

    def get_pdus_after_transaction(self, transaction_id, destination):
        return self._db_pool.runInteraction(
            PduQueries.get_after_transaction,
            transaction_id, destination
        )

    def get_pagination(self, context, pdu_list, limit):
        return self._db_pool.runInteraction(
            PduQueries.paginate,
            context, pdu_list, limit
        )

    def get_min_depth_for_context(self, context):
        return self._db_pool.runInteraction(
            PduQueries.get_min_depth,
            context
        )

    def update_min_depth_for_context(self, context, depth):
        return self._db_pool.runInteraction(
            PduQueries.update_min_depth,
            context, depth
        )

    def get_latest_pdus_in_context(self, context):
        return self._db_pool.runInteraction(
            PduQueries.get_prev_pdus,
            context
        )

    def get_oldest_pdus_in_context(self, context):
        return self._db_pool.runInteraction(
            PduQueries.get_back_extremities,
            context
        )

    def get_unresolved_state_tree(self, new_state_pdu):
        return self._db_pool.runInteraction(
            StateQueries.get_unresolved_state_tree,
            new_state_pdu
        )

    def update_current_state(self, pdu_id, origin, context, pdu_type,
                             state_key):
        return self._db_pool.runInteraction(
            StateQueries.update_current_state,
            pdu_id, origin, context, pdu_type, state_key
        )

    def is_pdu_new(self, pdu_id, origin, context, depth):
        return self._db_pool.runInteraction(
            PduQueries.is_new,
            pdu_id=pdu_id,
            origin=origin,
            context=context,
            depth=depth
        )
