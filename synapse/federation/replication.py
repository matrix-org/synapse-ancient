# -*- coding: utf-8 -*-
"""This layer is responsible for replicating with remote home servers using
a given transport.
"""

from twisted.internet import defer

from .units import Transaction, Pdu

from .persistence import PduActions, TransactionActions
from synapse.persistence.transactions import PduQueries

from synapse.util.logutils import log_function

import logging
import time

logger = logging.getLogger(__name__)


class ReplicationLayer(object):
    """This layer is responsible for replicating with remote home servers over
    the given transport. I.e., does the sending and receiving of PDUs to
    remote home servers.

    The layer communicates with the rest of the server via a registered
    ReplicationHandler.

    In more detail, the layer:
        * Receives incoming data and processes it into transactions and pdus.
        * Fetches any PDUs it thinks it might have missed.
        * Keeps the current state for contexts up to date by applying the
          suitable conflict resolution.
        * Sends outgoing pdus wrapped in transactions.
        * Fills out the references to previous pdus/transactions appropriately
          for outgoing data.
    """

    def __init__(self, hs, transport_layer):
        self.server_name = hs.hostname

        self.transport_layer = transport_layer
        self.transport_layer.register_received_handler(self)
        self.transport_layer.register_request_handler(self)

        self.persistence_service = hs.get_persistence_service()
        self.pdu_actions = PduActions(self.persistence_service)
        self.transaction_actions = TransactionActions(self.persistence_service)

        self._transaction_queue = _TransactionQueue(
            self.server_name,
            self.transaction_actions,
            transport_layer
        )

        self.handler = None

        self._order = 0

        self._db_pool = hs.get_db_pool()

    def set_handler(self, handler):
        """Sets the handler that the replication layer will use to communicate
        receipt of new PDUs from other home servers. The required methods are
        documented on :py:class:`.ReplicationHandler`.
        """
        self.handler = handler

    @defer.inlineCallbacks
    @log_function
    def send_pdu(self, pdu):
        """Informs the replication layer about a new PDU generated within the
        home server that should be transmitted to others.

        This will fill out various attributes on the PDU object, e.g. the
        `prev_pdus` key.

        *Note:* The home server should always call `send_pdu` even if it knows
        that it does not need to be replicated to other home servers. This is
        in case e.g. someone else joins via a remote home server and then
        paginates.

        TODO: Figure out when we should actually resolve the deferred.

        Args:
            pdu (Pdu): The new Pdu.

        Returns:
            Deferred: Completes when we have successfully processed the PDU
            and replicated it to any interested remote home servers.
        """
        order = self._order
        self._order += 1

        logger.debug("[%s] Persisting PDU", pdu.pdu_id)

        #yield self.pdu_actions.populate_previous_pdus(pdu)

        # Save *before* trying to send
        yield self.pdu_actions.persist_outgoing(pdu)

        logger.debug("[%s] Persisted PDU", pdu.pdu_id)
        logger.debug("[%s] transaction_layer.enqueue_pdu... ", pdu.pdu_id)

        yield self._transaction_queue.enqueue_pdu(pdu, order)

        logger.debug("[%s] transaction_layer.enqueue_pdu... done", pdu.pdu_id)

    @defer.inlineCallbacks
    @log_function
    def paginate(self, dest, context, limit):
        """Requests some more historic PDUs for the given context from the
        given destination server.

        Args:
            dest (str): The remote home server to ask.
            context (str): The context to paginate back on.
            limit (int): The maximum number of PDUs to return.

        Returns:
            Deferred: Results in the received PDUs.
        """
        extremities = yield self._db_pool.runInteraction(
            PduQueries.get_back_extremities,
            context
        )

        logger.debug("paginate extrem=%s", extremities)

        # If there are no extremeties then we've (probably) reached the start.
        if not extremities:
            return

        transaction_data = yield self.transport_layer.paginate(
            dest, context, extremities, limit)

        logger.debug("paginate transaction_data=%s", repr(transaction_data))

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=False, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    @log_function
    def get_pdu(self, destination, pdu_origin, pdu_id, outlier=False):
        """Requests the PDU with given origin and ID from the remote home
        server.

        This will persist the PDU locally upon receipt.

        Args:
            destination (str): Which home server to query
            pdu_origin (str): The home server that originally sent the pdu.
            pdu_id (str)
            outlier (bool): Indicates whether the PDU is an `outlier`, i.e. if
                it's from an arbitary point in the context as opposed to part
                of the current block of PDUs. Defaults to `False`

        Returns:
            Deferred: Results in the requested PDU.
        """

        transaction_data = yield self.transport_layer.get_pdu(
            destination, pdu_origin, pdu_id)

        transaction = Transaction(**transaction_data)

        pdu_list = [Pdu(outlier=outlier, **p) for p in transaction.pdus]

        pdu = None
        if pdu_list:
            pdu = pdu_list[0]
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdu)

    @defer.inlineCallbacks
    @log_function
    def get_state_for_context(self, destination, context):
        """Requests all of the `current` state PDUs for a given context from
        a remote home server.

        Args:
            destination (str): The remote homeserver to query for the state.
            context (str): The context we're interested in.

        Returns:
            Deferred: Results in a list of PDUs.
        """

        transaction_data = yield self.transport_layer.get_context_state(
            destination, context)

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=True, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    @log_function
    def on_paginate_request(self, context, versions, limit):

        pdus = yield self.pdu_actions.paginate(context, versions, limit)

        defer.returnValue((200, self._transaction_from_pdus(pdus).get_dict()))

    @defer.inlineCallbacks
    @log_function
    def on_incoming_transaction(self, transaction_data):
        transaction = Transaction(**transaction_data)

        logger.debug("[%s] Got transaction", transaction.transaction_id)

        response = yield self.transaction_actions.have_responded(transaction)

        if response:
            logger.debug("[%s] We've already responed to this request",
                         transaction.transaction_id)
            defer.returnValue(response)
            return

        logger.debug("[%s] Transacition is new", transaction.transaction_id)

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

        yield self.transaction_actions.set_response(
            transaction,
            200, response
        )
        defer.returnValue((200, response))

    @defer.inlineCallbacks
    @log_function
    def on_context_state_request(self, context):
        results = yield self.persistence_service.get_current_state_for_context(
            context
        )

        logger.debug("Context returning %d results", len(results))

        pdus = [Pdu.from_pdu_tuple(p) for p in results]
        defer.returnValue((200, self._transaction_from_pdus(pdus).get_dict()))

    @defer.inlineCallbacks
    @log_function
    def on_pdu_request(self, pdu_origin, pdu_id):
        pdu = yield self._get_persisted_pdu(pdu_id, pdu_origin)

        if pdu:
            defer.returnValue(
                (200, self._transaction_from_pdus([pdu]).get_dict())
            )
        else:
            defer.returnValue((404, ""))

    @defer.inlineCallbacks
    @log_function
    def on_pull_request(self, origin, versions):
        transaction_id = max([int(v) for v in versions])

        response = yield self.pdu_actions.after_transaction(
            transaction_id,
            origin,
            self.server_name
        )

        if not response:
            response = []

        defer.returnValue(
            (200, self._transaction_from_pdus(response).get_dict())
        )

    @defer.inlineCallbacks
    @log_function
    def _get_persisted_pdu(self, pdu_id, pdu_origin):
        """ Get a PDU from the database with given origin and id.

        Returns:
            Deferred: Results in a `Pdu`.
        """
        pdu_tuple = yield self.persistence_service.get_pdu(pdu_id, pdu_origin)

        defer.returnValue(Pdu.from_pdu_tuple(pdu_tuple))

    def _transaction_from_pdus(self, pdu_list):
        """Returns a new Transaction containing the given PDUs suitable for
        transmission.
        """
        return Transaction(
            pdus=[p.get_dict() for p in pdu_list],
            origin=self.server_name,
            ts=int(time.time() * 1000),
            destination=None,
        )

    @defer.inlineCallbacks
    @log_function
    def _handle_new_pdu(self, pdu):
        # We reprocess pdus when we have seen them only as outliers
        existing = yield self._get_persisted_pdu(pdu.pdu_id, pdu.origin)

        if existing and (not existing.outlier or pdu.outlier):
            logger.debug("Already seen pdu %s %s", pdu.pdu_id, pdu.origin)
            defer.returnValue({})
            return

        # Get missing pdus if necessary.
        is_new = yield self.pdu_actions.is_new(pdu)
        if is_new and not pdu.outlier:
            # We only paginate backwards to the min depth.
            min_depth = yield self._db_pool.runInteraction(
                PduQueries.get_min_depth,
                pdu.context
            )

            if min_depth and pdu.depth > min_depth:
                for pdu_id, origin in pdu.prev_pdus:
                    exists = yield self._get_persisted_pdu(pdu_id, origin)

                    if not exists:
                        logger.debug("Requesting pdu %s %s", pdu_id, origin)

                        yield self.get_pdu(
                            pdu.origin,
                            pdu_id=pdu_id,
                            pdu_origin=origin
                        )
                        logger.debug("Processed pdu %s %s", pdu_id, origin)

        # Persist the Pdu, but don't mark it as processed yet.
        yield self.pdu_actions.persist_received(pdu)

        ret = yield self.handler.on_receive_pdu(pdu)

        yield self.pdu_actions.mark_as_processed(pdu)

        defer.returnValue(ret)

    def __str__(self):
        return "<ReplicationLayer(%s)>" % self.server_name


class ReplicationHandler(object):
    """This defines the methods that the :py:class:`.ReplicationLayer` will
    use to communicate with the rest of the home server.
    """
    def on_receive_pdu(self, pdu):
        raise NotImplementedError("on_receive_pdu")


class _TransactionQueue(object):
    """This class makes sure we only have one transaction in flight at
    a time for a given destination.

    It batches pending PDUs into single transactions.
    """

    def __init__(self, server_name, transaction_actions, transport_layer):

        self.server_name = server_name
        self.transaction_actions = transaction_actions
        self.transport_layer = transport_layer

        # Is a mapping from destinations -> deferreds. Used to keep track
        # of which destinations have transactions in flight and when they are
        # done
        self.pending_transactions = {}

        # Is a mapping from destination -> list of
        # tuple(pending pdus, deferred, order)
        self.pending_pdus_list = {}

    @defer.inlineCallbacks
    @log_function
    def enqueue_pdu(self, pdu, order):
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        destinations = [
            d for d in pdu.destinations
            if d != self.server_name
        ]

        logger.debug("Sending to: %s", str(destinations))

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
    @log_function
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

            yield self.transaction_actions.prepare_to_send(transaction)

            logger.debug("TX [%s] Persisted transaction", destination)
            logger.debug("TX [%s] Sending transaction...", destination)

            # Actually send the transaction
            code, response = yield self.transport_layer.send_transaction(
                transaction
            )

            logger.debug("TX [%s] Sent transaction", destination)
            logger.debug("TX [%s] Marking as delivered...", destination)

            yield self.transaction_actions.delivered(
                transaction, code, response
            )

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
