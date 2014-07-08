# -*- coding: utf-8 -*-

from twisted.internet import defer

from .units import Transaction, Pdu

from synapse.persistence.transactions import (
    PduQueries, StateQueries, run_interaction
)
from .persistence import PduActions, TransactionActions

import logging
import time

logger = logging.getLogger(__name__)


class ReplicationLayer(object):

    def __init__(self, server_name, transport_layer):
        self.server_name = server_name

        self.transport_layer = transport_layer
        self.transport_layer.register_received_handler(self)
        self.transport_layer.register_request_handler(self)

        self._transaction_queue = _TransactionQueue(
            server_name,
            transport_layer
        )

        self.handler = None

        self._order = 0

    def set_handler(self, handler):
        self.handler = handler

    @defer.inlineCallbacks
    def send_pdu(self, pdu):
        order = self._order
        self._order += 1

        logger.debug("[%s] Persisting PDU", pdu.pdu_id)

        yield PduActions.populate_previous_pdus(pdu)

        # Save *before* trying to send
        yield PduActions.persist_outgoing(pdu)

        logger.debug("[%s] Persisted PDU", pdu.pdu_id)
        logger.debug("[%s] transaction_layer.enqueue_pdu... ", pdu.pdu_id)

        yield self._transaction_queue.enqueue_pdu(pdu, order)

        logger.debug("[%s] transaction_layer.enqueue_pdu... done", pdu.pdu_id)

    @defer.inlineCallbacks
    def paginate(self, dest, context, limit):
        logger.debug("paginate context=%s, dest=%s", context, dest)
        extremities = yield run_interaction(
            PduQueries.get_back_extremities,
            context
        )

        logger.debug("paginate extrem=%s", extremities)

        if not extremities:
            return

        transaction_data = yield self.transport_layer.trigger_paginate(
            dest, context, extremities, limit)

        logger.debug("paginate transaction_data=%s", repr(transaction_data))

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=False, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def get_pdu(self, destination, pdu_origin, pdu_id, outlier=False):
        logger.debug("get_pdu dest=%s, pdu_origin=%s, pdu_id=%s",
                     destination, pdu_origin, pdu_id)

        transaction_data = yield self.transport_layer.trigger_get_pdu(
            destination, pdu_origin, pdu_id)

        transaction = Transaction(**transaction_data)

        pdu_list = [Pdu(outlier=outlier, **p) for p in transaction.pdus]

        pdu = None
        if pdu_list:
            pdu = pdu_list[0]
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdu)

    @defer.inlineCallbacks
    def get_state_for_context(self, destination, context):
        logger.debug(
            "get_state_for_context context=%s, dest=%s", context, destination)

        transaction_data = yield self.transport_layer.trigger_get_context_state(
            destination, context)

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=True, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def on_paginate_request(self, context, versions, limit):
        logger.debug(
            "on_paginate_request context=%s", context)

        pdus = yield PduActions.paginate(context, versions, limit)

        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_transaction(self, transaction_data):
        transaction = Transaction(**transaction_data)

        logger.debug("[%s] Got transaction", transaction.transaction_id)

        response = yield TransactionActions.have_responded(transaction)

        if response:
            logger.debug("[%s] We've already responed to this request",
                         transaction.transaction_id)
            defer.returnValue(response)
            return

        logger.debug("[%s] Transacition is new", transaction.transaction_id)

        try:
            pdu_list = [Pdu(**p) for p in transaction.pdus]

            dl = []
            for pdu in pdu_list:
                dl.append(self._handle_new_pdu(pdu))

            results = yield defer.DeferredList(dl)

            ret = []
            for r in results:
                if r[0]:
                    ret.append({})
                else:
                    logger.exception(r[1])
                    ret.append({"error": str(r[1])})

            logger.debug("Returning: %s", str(ret))

            yield TransactionActions.set_response(transaction, 200, response)
            defer.returnValue((200, response))
        except Exception as e:
            logger.exception(e)

            # We don't save a 500 response!

            defer.returnValue((500, {"error": "Internal server error"}))
            return

    @defer.inlineCallbacks
    def on_context_state_request(self, context):
        logger.debug("on_context_state_request context=%s", context)
        pdus = yield PduActions.current_state(context)
        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        logger.debug(
            "on_pdu_request pdu_origin=%s, pdu_id=%s", pdu_origin, pdu_id)

        pdu = yield PduActions.get_persisted_pdu(pdu_id, pdu_origin)

        pdus = []
        if not pdu:
            pdus = [pdu]

        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_pull_request(self, origin, versions):
        logger.debug("on_pull_request origin=%s", origin)

        transaction_id = max([int(v) for v in versions])

        response = yield PduActions.after_transaction(
            transaction_id,
            origin,
            self.server_name
        )

        if not response:
            response = []

        defer.returnValue((200, self._wrap_pdus(response)))

    def _wrap_pdus(self, pdu_list):
        return Transaction(
            pdus=[p.get_dict() for p in pdu_list],
            origin=self.server_name,
            ts=int(time.time() * 1000),
            destination=None,
        ).get_dict()

    @defer.inlineCallbacks
    def _handle_new_pdu(self, pdu):
        logger.debug(
            "_handle_new_pdu %s from %s", str(pdu.pdu_id), pdu.origin
        )

        # We reprocess pdus when we have seen them only as outliers
        existing = yield PduActions.get_persisted_pdu(pdu.pdu_id, pdu.origin)
        if existing and (not existing.outlier or pdu.outlier):
            defer.returnValue({})
            return

        # Get missing pdus if necessary.
        is_new = yield PduActions.is_new(pdu)
        if is_new and not pdu.outlier:
            # We only paginate backwards to the min depth.
            min_depth = yield run_interaction(
                PduQueries.get_min_depth,
                pdu.context
            )

            if min_depth and pdu.depth > min_depth:
                for pdu_id, origin in pdu.prev_pdus:
                    exists = yield PduActions.get_persisted_pdu(pdu_id, origin)
                    if not exists:
                        logger.debug("Requesting pdu %s %s", pdu_id, origin)

                        yield self.get_pdu(
                            pdu.origin,
                            pdu_id=pdu_id,
                            pdu_origin=origin
                        )
                        logger.debug("Processed pdu %s %s", pdu_id, origin)

        # Persist the Pdu, but don't mark it as processed yet.
        yield PduActions.persist_received(pdu)

        if pdu.is_state:
            res = yield self._handle_state(pdu, existing)
            defer.returnValue(res)
            return
        else:
            ret = yield self.handler.on_receive_pdu(pdu)

            yield PduActions.mark_as_processed(pdu)

            defer.returnValue(ret)

    @defer.inlineCallbacks
    def _handle_state(self, pdu, existing):
        logger.debug(
            "_handle_state pdu: %s %s",
            pdu.pdu_id, pdu.origin
        )

        if not existing:
            # Work out if the state has changed. If so hit the state change
            # callback.

            # XXX: RACES?!

            # Fetch any missing state pdus we might be missing
            while True:
                r = yield run_interaction(
                    StateQueries.get_next_missing_pdu,
                    pdu
                )
                if r:
                    logger.debug(
                        "_handle_state getting pdu: %s %s",
                        r.pdu_id, r.origin
                    )
                    yield self.get_pdu(
                        pdu.origin,
                        pdu_id=r.pdu_id,
                        origin=r.origin,
                        outlier=True
                    )
                else:
                    break

            logger.debug("_handle_state updating state")

            was_updated = yield run_interaction(
                StateQueries.handle_new_state,
                pdu
            )

            logger.debug("_handle_state was_updated %s", repr(was_updated))

            if was_updated:
                logger.debug(
                    "Notifying about new state: %s %s",
                    pdu.pdu_id, pdu.origin
                )
                yield self.handler.on_state_change(pdu)

        if not pdu.outlier:
            logger.debug(
                "Notifying about new pdu: %s %s",
                pdu.pdu_id, pdu.origin
            )

            # Inform callback
            ret = yield self.handler.on_receive_pdu(pdu)

            # Mark this Pdu as processed
            yield PduActions.mark_as_processed(pdu)

            defer.returnValue(ret)
        else:
            defer.returnValue({})


class ReplicationHandler(object):
    def on_receive_pdu(self, pdu):
        raise NotImplementedError("on_receive_pdu")

    def on_state_change(self, pdu):
        raise NotImplementedError("on_state_change")


class _TransactionQueue(object):
    """ This class makes sure we only have one transaction in flight at
        a time for a given destination.

        It batches pending PDUs into single transactions.
    """

    def __init__(self, server_name, transport_layer):

        self.server_name = server_name
        self.transport_layer = transport_layer

        # Is a mapping from destinations -> deferreds. Used to keep track
        # of which destinations have transactions in flight and when they are
        # done
        self.pending_transactions = {}

        # Is a mapping from destination -> list of
        # tuple(pending pdus, deferred, order)
        self.pending_pdus_list = {}

    @defer.inlineCallbacks
    def enqueue_pdu(self, pdu, order):
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        destinations = [
            d for d in pdu.destinations
            if d != self.server_name
        ]

        logger.debug("Sending to: %s" % str(destinations))

        if not destinations:
            return

        deferred_list = []

        for destination in destinations:
            deferred = defer.Deferred()
            self.pending_pdus_list.setdefault(destination, []).append(
                (pdu, deferred, order)
            )

            self._attempt_new_transaction(destination)

            yield deferred_list.append(deferred)

    @defer.inlineCallbacks
    def _attempt_new_transaction(self, destination):
        if destination in self.pending_transactions:
            return

        # tuple_list is a list of (pending_pdu, deferred, order)
        tuple_list = self.pending_pdus_list.pop(destination, None)

        if not tuple_list:
            return

        logger.debug("TX [%s] Attempting new transaction", destination)

        try:
            # Sort based on the order field
            tuple_list.sort(key=lambda t: t[2])

            logger.debug("TX [%s] Persisting transaction...", destination)

            pdus = [p[0] for p in tuple_list]

            transaction = Transaction.create_new(
                origin=self.server_name,
                destination=destination,
                pdus=pdus,
            )

            yield TransactionActions.prepare_to_send(transaction)

            logger.debug("TX [%s] Persisted transaction", destination)
            logger.debug("TX [%s] Sending transaction...", destination)

            # Actually send the transaction
            code, response = yield self.transport_layer.send_transaction(
                transaction
            )

            logger.debug("TX [%s] Sent transaction", destination)
            logger.debug("TX [%s] Marking as delivered...", destination)

            yield TransactionActions.delivered(transaction, code, response)

            logger.debug("TX [%s] Marked as delivered", destination)
            logger.debug("TX [%s] Yielding to callbacks...", destination)

            for _, deferred, _ in tuple_list:
                if code == 200:
                    deferred.callback(None)
                else:
                    deferred.errback(RuntimeError("Got status %d" % code))

                # Ensures we don't continue until all callbacks on that
                # deferred have fired
                yield deferred

            logger.debug("TX [%s] Yielded to callbacks", destination)

        except Exception as e:
            logger.error("TX Problem in _attempt_transaction")

            # We capture this here as there as nothing actually listens
            # for this finishing functions deferred.
            logger.exception(e)

            for _, deferred, _ in tuple_list:
                deferred.errback(e)
                yield deferred

        finally:
            # We want to be *very* sure we delete this after we stop processing
            self.pending_transactions.pop(destination, None)

            # Check to see if there is anything else to send.
            self._attempt_new_transaction(destination)
