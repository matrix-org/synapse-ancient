# -*- coding: utf-8 -*-
""" This module contains all the persistence actions done by the federation
package.

These actions are mostly only used by the :py:mod:`.replication` module.
"""

from twisted.internet import defer

from synapse.persistence.transactions import (
    TransactionQueries, PduQueries,
    StateQueries, run_interaction
)

from .units import Pdu

import copy
import json
import logging


logger = logging.getLogger(__name__)


class PduActions(object):
    """ Defines persistence actions that relate to handling PDUs.
    """

    @staticmethod
    @defer.inlineCallbacks
    def current_state(context):
        """ For the given context return what we think is the current state.

        Returns:
            Deferred: Results in a list of state `Pdu`s.
        """
        results = yield run_interaction(
            PduQueries.get_current_state,
            context
        )

        defer.returnValue([Pdu.from_pdu_tuple(p) for p in results])

    @staticmethod
    @defer.inlineCallbacks
    def get_persisted_pdu(pdu_id, pdu_origin):
        """ Get a PDU from the database with given origin and id.

        Returns:
            Deferred: Results in a `Pdu`.
        """
        pdu_tuple = yield run_interaction(
            PduQueries.get_pdu,
            pdu_id, pdu_origin
        )

        defer.returnValue(Pdu.from_pdu_tuple(pdu_tuple))

    @classmethod
    def persist_received(cls, pdu):
        """ Persists the given `Pdu` that was received from a remote home
        server.

        Returns:
            Deferred
        """
        return cls._persist(pdu)

    @classmethod
    @defer.inlineCallbacks
    def persist_outgoing(cls, pdu):
        """ Persists the given `Pdu` that this home server created.

        Returns:
            Deferred
        """
        ret = yield cls._persist(pdu)

        # This is safe to do since if *we* are sending something, then we must
        # have seen everything we reference (hopefully).
        if pdu.is_state:
            yield run_interaction(
                StateQueries.handle_new_state,
                pdu
            )

        defer.returnValue(ret)

    @staticmethod
    def mark_as_processed(pdu):
        """ Persist the fact that we have fully processed the given `Pdu`

        Returns:
            Deferred
        """
        return run_interaction(
            PduQueries.mark_as_processed,
            pdu.pdu_id, pdu.origin
        )

    @classmethod
    @defer.inlineCallbacks
    def populate_previous_pdus(cls, pdu):
        """ Given an outgoing `Pdu` fill out its `prev_ids` key with the `Pdu`s
        that we have received.

        Returns:
            Deferred
        """
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
        """ Returns all `Pdu`s that we sent to the given remote home server
        after a given transaction id.

        Returns:
            Deferred: Results in a list of `Pdu`s
        """
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
        """ For a given list of PDU id and origins return the proceeding
        `limit` `Pdu`s in the given `context`.

        Returns:
            Deferred: Results in a list of `Pdu`s.
        """
        results = yield run_interaction(
            PduQueries.paginate,
            context, pdu_list, limit
        )

        defer.returnValue([Pdu.from_pdu_tuple(p) for p in results])

    @staticmethod
    def is_new(pdu):
        """ When we receive a `Pdu` from a remote home server, we want to
        figure out whether it is `new`, i.e. it is not some historic PDU that
        we haven't seen simply because we haven't paginated back that far.

        Returns:
            Deferred: Results in a `bool`
        """
        return run_interaction(
            PduQueries.is_new,
            pdu_id=pdu.pdu_id,
            origin=pdu.origin,
            context=pdu.context,
            depth=pdu.depth
        )

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


class TransactionActions(object):
    """ Defines persistence actions that relate to handling Transactions.
    """

    @staticmethod
    def have_responded(transaction):
        """ Have we already responded to a transaction with the same id and
        origin?

        Returns:
            Deferred: Results in `None` if we have not previously responded to
            this transaction or a 2-tuple of `(int, dict)` representing the
            response code and response body.
        """
        if not transaction.transaction_id:
            raise RuntimeError("Cannot persist a transaction with no "
                               "transaction_id")

        return run_interaction(
            TransactionQueries.get_response_for_received,
            transaction.transaction_id, transaction.origin
        )

    @staticmethod
    def set_response(transaction, code, response):
        """ Persist how we responded to a transaction.

        Returns:
            Deferred
        """
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
    @defer.inlineCallbacks
    def prepare_to_send(transaction):
        """ Persists the `Transaction` we are about to send and works out the
        correct value for the `prev_ids` key.

        Returns:
            Deferred
        """
        transaction.prev_ids = yield run_interaction(
            TransactionQueries.prep_send_transaction,
            transaction.transaction_id,
            transaction.destination,
            transaction.ts,
            [(p["pdu_id"], p["origin"]) for p in transaction.pdus]
        )

    @staticmethod
    def delivered(transaction, response_code, response_dict):
        """ Marks the given `Transaction` as having been successfully
        delivered to the remote homeserver, and what the response was.

        Returns:
            Deferred
        """
        return run_interaction(
            TransactionQueries.delivered_txn,
            transaction.transaction_id,
            transaction.destination,
            response_code,
            json.dumps(response_dict)
        )