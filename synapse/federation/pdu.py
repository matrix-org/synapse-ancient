# -*- coding: utf-8 -*-
""" The PDU layer is responsible for handling:
    - duplicate PDU ids
    - responding to requests for particular PDUs
    - responding to requests for current state PDUs for a given context
    - "versioning" outgoing PDUs by filling out `previous_pdus` property
    - Ensuring for incoming PDUs we have seen all the PDUs it references
"""

from twisted.internet import defer

from .transaction import TransactionCallbacks
from .protocol.units import Pdu
from synapse.persistence.transactions import (
    PduQueries, StateQueries, run_interaction
)

import logging


logger = logging.getLogger(__name__)


class PduCallbacks(object):
    """ A callback interface used by the PduLayer to inform layers above about
    new PDUs.
    """

    def on_receive_pdu(self, pdu):
        """ We received a PDU. Someone should handle that.

        Args:
            pdu (synapse.federation.protocol.units.Pdu): The PDU we received.

        Returns:
            Deferred: Results in a dict that used as the response to the PDU.
        """
        pass

    def on_state_change(self, pdu):
        """ A state change occured.

        Args:
            pdu (synapse.federation.protocol.units.Pdu): The pdu of the new
                state.

        Returns:
            Deferred
        """
        pass


class PduLayer(TransactionCallbacks):
    """
    Attributes:
        transaction_layer (synapse.transaction.TransactionLayer): The
            transaction layer we use to to send PDUs.

        callback (synapse.pdu.PduCallbacks): The currently registered callback.
    """

    def __init__(self, transaction_layer):
        """
        Args:
            transaction_layer (synapse.transaction.TransactionLayer): The
                transaction layer we use to to send PDUs.
        """

        self.transaction_layer = transaction_layer

        self.transaction_layer.set_callback(self)

        self.callback = None

        self._order = 0

    def set_callback(self, callback):
        self.callback = callback

    @defer.inlineCallbacks
    def send_pdu(self, pdu):
        """ Sends a PDU. This takes care of handling the versions.

        Args:
            pdu (synapse.federation.protocol.units.Pdu): The PDU to send

        Returns:
            Deferred: That succeeds when we have successfully sent the PDU

        """
        # We need to define the ordering *before* we yield to set the new
        # version.
        order = self._order
        self._order += 1

        logger.debug("[%s] Persisting PDU", pdu.pdu_id)

        yield pdu.populate_previous_pdus()

        # Save *before* trying to send
        yield pdu.persist_outgoing()

        logger.debug("[%s] Persisted PDU", pdu.pdu_id)
        logger.debug("[%s] transaction_layer.enqueue_pdu... ", pdu.pdu_id)

        yield self.transaction_layer.enqueue_pdu(pdu, order)

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

        res = yield self.transaction_layer.trigger_paginate(
            dest, context, extremities, limit)

        defer.returnValue(res)

    @defer.inlineCallbacks
    def on_received_pdus(self, pdu_list):
        """
        Overrides:
            TransactionCallbacks
        """
        pdu_list = [Pdu(**p) for p in pdu_list]

        # We got a bunch of pdus. Handle them "concurrently" (i.e., don't
        # indvidually yield), so pass them off to the _handle_new_pdu and then
        # yield on the deferred list
        dl = []
        for pdu in pdu_list:
            dl.append(self._handle_new_pdu(pdu))

        results = yield defer.DeferredList(dl)

        # Generate an appropriate return value from the DeferredList results
        ret = []
        for r in results:
            if r[0]:
                ret.append({})
            else:
                logger.exception(r[1])
                ret.append({"error": str(r[1])})

        logger.debug("Returning: %s", str(ret))

        defer.returnValue((200, ret))

    @defer.inlineCallbacks
    def on_context_state_request(self, context):
        """
        Overrides:
            TransactionCallbacks
        """

        pdus = yield Pdu.current_state(context)
        defer.returnValue([p.get_dict() for p in pdus])

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """
        Overrides:
            TransactionCallbacks
        """

        pdu = yield Pdu.get_persisted_pdu(pdu_id, pdu_origin)

        if not pdu:
            defer.returnValue(None)
            return

        defer.returnValue(pdu.get_dict())

    @defer.inlineCallbacks
    def on_paginate_request(self, context, pdus, limit):
        """
        Overrides:
            TransactionCallbacks
        """

        pdus = yield Pdu.paginate(context, pdus, limit)
        defer.returnValue([p.get_dict() for p in pdus])

    @defer.inlineCallbacks
    def on_pull_request(self, transaction_id, origin):
        """
        Overrides:
            TransactionCallbacks
        """
        response = yield Pdu.after_transaction(
            transaction_id,
            origin,
            self.server_name
        )

        if not response:
            response = []

        defer.returnValue([p.get_dict() for p in response])

    @defer.inlineCallbacks
    def _handle_new_pdu(self, pdu):
        logger.debug(
            "_handle_new_pdu %s from %s", str(pdu.pdu_id), pdu.origin
        )

        # Check if we've seen it before. If we have then we ignore
        # it (unless we have only seen an outlier before)
        existing = yield Pdu.get_persisted_pdu(pdu.pdu_id, pdu.origin)
        if existing and (not existing.outlier or pdu.outlier):
            # We've already seen it, so we ignore it.
            defer.returnValue({})
            return

        # If we are a "new" pdu, we check to see if we have seen the pdus
        # it references. (Unless we are an outlier)
        is_new = yield pdu.is_new()
        if is_new and not pdu.outlier:
            # We only paginate backwards if we seem to be missing something
            # that is before the current min_depth for a context - i.e.,
            # we don't want to paginate backwards.

            min_depth = yield run_interaction(
                PduQueries.get_min_depth,
                pdu.context
            )

            # If min_depth is None, that means that we haven't seen this
            # context before, so we don't go backwards yet.
            if min_depth and pdu.depth > min_depth:
                for pdu_id, origin in pdu.prev_pdus:
                    exists = yield Pdu.get_persisted_pdu(pdu_id, origin)
                    if not exists:
                        # Oh no! We better request it.
                        yield self.transaction_layer.trigger_get_pdu(
                            pdu.origin,
                            pdu_id=pdu_id,
                            pdu_origin=origin,
                            outlier=pdu.outlier
                        )

        # Persist the Pdu, but don't mark it as processed yet.
        yield pdu.persist_received()

        # XXX: Do we want to temporarily persist here, instead of waiting
        # for us to fetch any missing Pdus?

        if pdu.is_state:
            res = yield self._handle_state(pdu, existing)
            defer.returnValue(res)
            return
        else:
            ret = yield self.callback.on_receive_pdu(pdu)

            yield pdu.mark_as_processed()

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
                    yield self.transaction_layer.trigger_get_pdu(
                        pdu.origin,
                        pdu_id=r.pdu_id,
                        origin=r.origin,
                        outlier=True,
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
                yield self.callback.on_state_change(pdu)

        if not pdu.outlier:
            logger.debug(
                "Notifying about new pdu: %s %s",
                pdu.pdu_id, pdu.origin
            )

            # Inform callback
            ret = yield self.callback.on_receive_pdu(pdu)

            # Mark this Pdu as processed
            yield pdu.mark_as_processed()

            defer.returnValue(ret)
        else:
            defer.returnValue({})
