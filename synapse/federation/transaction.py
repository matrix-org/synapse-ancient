# -*- coding: utf-8 -*-
""" The transaction layer is responsible for handling incoming and outgoing
transactions, as well as other events (e.g. requests for a specific
pdu)

For incoming transactions it needs to ignore duplicates, and otherwise
pass the data upwards. It receives incoming transactions (and other
events) via the Transport.TransportCallbacks.
For incoming events it usually passes the request directly onwards

For outgoing transactions, it needs to convert it to a suitable form
for the Transport layer to process.
For outgoing events, we usually pass it straight to the Transport layer
"""

from twisted.internet import defer

from .transport import TransportReceivedCallbacks, TransportRequestCallbacks
from .protocol.units import Transaction, Pdu

import logging
import time


logger = logging.getLogger(__name__)


class PduDecodeException(Exception):
    pass


class TransactionCallbacks(object):
    """ Get's called when the transaction layer receives new data, or needs to
    request data to handle requests.
    """

    def on_received_pdus(self, pdu_list):
        """ Get's called when we receive pdus via a transaction.

        Args:
            pdu_list (list): A list of synapse.federation.protocol.units.Pdu
                that we received as part of a transaction

        Returns:
            Deferred: Called back when they have been
            successfully processed *and* persisted, or errbacks with either
            a) PduDecodeException, at which point we return a 400 on the
            entire transaction, or b) another exception at which point we
            respond with a 500 to the entire transaction.
        """
        pass

    def on_context_state_request(self, context):
        """ Called on GET /state/<context>/ from transport layer

        Args:
            context (str): The name of the context to get the current state of

        Returns:
            Deferred: Results in a tuple of (code, response), where `response`
            should be a list of dicts representing the current state Pdu's
            for the given context
        """
        pass

    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer

        Args:
            pdu_origin (str): The origin of the Pdu being requested.

            pdu_id (str): The id of the Pdu being requested.

        Returns:
            Deferred: Results in a dict representing a PDU, or
            `None` if we couldn't find a matching Pdu.
        """
        pass

    def on_paginate_request(self, context, versions, limit):
        """ Called on GET /paginate/<context>/?v=...&limit=...

        Get's hit when we want to paginate backwards on a given context from
        the given point.

        Args:
            context (str): The context to paginate on
            versions (list): A list of 2-tuple's representing where to paginate
                from, in the form `(pdu_id, origin)`
            limit (int): How many pdus to return.

        Returns:
            twisted.internet.defer.Deferred: A deferred that get's fired when
            we have a response ready to send.

            The result should be a tuple in the form of
            `(response_code, respond_body)`, where `response_body` is a python
            dict that will get serialized to JSON.

            On errors, the dict should have an `error` key with a brief message
            of what went wrong.
        """
        pass

    def get_pdus_after_transaction(self, transaction_id, origin):
        """ Called when we want to get a pull request, and so want to get all
        the PDUs that were sent to the given destination after a given
        transaction id.

        Args:
            transaction_id (str)
            origin (str)

        Returns:
            Deferred: Results in a list of `dict`s representing the appropriate
            PDUs.
        """
        pass


class TransactionLayer(TransportReceivedCallbacks, TransportRequestCallbacks):
    """ The transaction layer is responsible for handling incoming and outgoing
    transactions, as well as other events (e.g. requests for a specific
    pdu)

    For incoming transactions it needs to ignore duplicates, and otherwise
    pass the data upwards. It receives incoming transactions (and other
    events) via the Transport.TransportCallbacks.
    For incoming events it usually passes the request directly onwards

    For outgoing transactions, it needs to convert it to a suitable form
    for the Transport layer to process.
    For outgoing events, we usually pass it straight to the Transport layer

    Attributes:
        server_name (str): Local home server host

        transport_layer (synapse.transport.TransportLayer): The transport
            layer to use.

        callback (synapse.transaction.TransactionCallbacks): The callback
            that gets triggered when we either a) have new data or b) have
            received a request that transaction layer doesn't handle.
    """

    def __init__(self, server_name, transport_layer):
        """
        Args:
            server_name (str): Local home server host

            transport_layer (synapse.transport.TransportLayer): The transport
                layer to use.
        """
        self.server_name = server_name

        self.transport_layer = transport_layer
        self.transport_layer.register_received_callbacks(self)
        self.transport_layer.register_request_callbacks(self)

        self.callback = None

        # Responsible for batching pdus
        self._transaction_queue = _TransactionQueue(
            server_name,
            transport_layer
        )

    def enqueue_pdu(self, pdu, order):
        """ Schedules the pdu to be sent.

        The order is an integer which defines the order in which pdus
        will be sent (ones with a larger order come later). This is to
        make sure we maintain the ordering defined by the versions without
        having to know what the versions look like at this layer.

        Args:
            pdu (synapse.federation.protocol.units.Pdu): The pdu we want to
                send.

            order (int): An integer that is used to order the sending of Pdus
                to the same remote home server

        Returns:
            Deferred: Succeeds when the Pdu has successfully been sent.

        """
        self._transaction_queue.enqueue_pdu(pdu, order)

    def _wrap_pdus(self, pdu_list):
        return Transaction(
            pdus=pdu_list,
            origin=self.server_name,
            ts=int(time.time() * 1000)
        ).get_dict()

    def set_callback(self, callback):
        """ Set's the callback.

        Args:
            callback (synapse.transaction.TransactionCallbacks):
        """
        self.callback = callback

    @defer.inlineCallbacks
    def on_pull_request(self, origin, versions):
        """ Called on GET /pull/ from transport layer

        Overrides:
            TransportReceivedCallbacks
        """

        # We know that we're the only node, so we assume that they're
        # integers and thus can just take the max
        tx_id = max([int(v) for v in versions])

        response = yield self.callback.get_pdus_after_transaction(
            tx_id, origin)

        if not response:
            response = []

        data = self._wrap_pdus(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer
        Returns a deferred tuple of (code, response)

        Overrides:
            TransportReceivedCallbacks
        """
        response = yield self.callback.on_pdu_request(pdu_origin, pdu_id)

        if response:
            data = self._wrap_pdus([response])
        else:
            data = self._wrap_pdus([])

        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_context_state_request(self, context):
        """ Called on GET /state/<context>/ from transport layer
        Returns a deferred tuple of (code, response)

        Overrides:
            TransportReceivedCallbacks
        """
        response = yield self.callback.on_context_state_request(context)

        data = self._wrap_pdus(response)

        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_transaction(self, transaction):
        """ Called on PUT /send/<transaction_id> from transport layer

        Overrides:
            TransportReceivedCallbacks
        """

        # TODO: We need to deal with us rapidly getting retransmits (we can't
        #     rely solely on have_responded)

        logger.debug("[%s] Got transaction", transaction.transaction_id)

        # Check to see if we a) have a transaction_id associated with this
        # request and if so b) have we already responded to it?
        response = yield transaction.have_responded()

        if response:
            logger.debug("[%s] We've already responed to this request",
                         transaction.transaction_id)
            defer.returnValue(response)
            return

        logger.debug("[%s] Transacition is new", transaction.transaction_id)

        # Pass request to transaction layer.
        try:
            code, response = yield self.callback.on_received_pdus(
                transaction.pdus
            )
        except PduDecodeException as e:
            # Problem decoding one of the PDUs, BAIL BAIL BAIL
            logger.exception(e)
            code = 400
            response = {"error": str(e)}
        except Exception as e:
            logger.exception(e)

            # We don't save a 500 response!

            defer.returnValue((500, {"error": "Internal server error"}))
            return

        yield transaction.set_response(code, response)
        defer.returnValue((code, response))

    @defer.inlineCallbacks
    def on_paginate_request(self, context, versions, limit):
        """
        Overrides:
            TransportRequestCallbacks
        """
        response = yield self.callback.on_paginate_request(
            context, versions, limit)

        data = self._wrap_pdus(response)

        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def trigger_get_context_state(self, destination, context):
        """Requests all state for a given context (i.e. room) from the
        given server.

        This will *not* return the state, but will pass the received state
        to the TransportReceivedCallbacks.on_transaction callback in the same
        way as if it had been sent them in a Transaction.

        Args:
            destination (str): The host name of the remote home server we want
                to get the state from.
            context (str): The name of the context we want the state of

        Returns:
            Deferred: Succeeds when we have finished processing the
            response of the request.

            The argument passed to the deferred is undefined and may be None.
        """
        logger.debug("trigger_get_context_metadata dest=%s, context=%s",
                     destination, context)

        transaction = yield self.transport_layer.trigger_get_context_state(
            destination, context)

        defer.returnValue(transaction.pdus)

    @defer.inlineCallbacks
    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Requests the pdu with give id and origin from the given server.

        This will *not* return the PDU, but will pass the received state
        to the TransportReceivedCallbacks.on_transaction callback in the same
        way as if it had been sent them in a Transaction.

        Args:
            destination (str): The host name of the remote home server we want
                to get the state from.
            pdu_origin (str): The home server which created the PDU.
            pdu_id (str): The id of the PDU being requested.
            outlier (bool): Should the returned PDUs be considered an outlier?
                Default: False

        Returns:
            Deferred: Succeeds when we have finished processing the
            response of the request.

            The result of the deferred is undefined and may be None.
        """
        logger.debug("trigger_get_pdu dest=%s, pdu_origin=%s, pdu_id=%s",
                     destination, pdu_origin, pdu_id)

        transaction = yield self.transport_layer.trigger_get_pdu(
            destination, pdu_origin, pdu_id)

        if transaction.pdus:
            defer.returnValue(transaction.pdus[0])
        else:
            defer.returnValue(None)

    @defer.inlineCallbacks
    def trigger_paginate(self, dest, context, pdu_tuples, limit):
        transaction = yield self.transport_layer.trigger_paginate(
            dest, context, pdu_tuples, limit)

        defer.returnValue(transaction.pdus)


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

            yield transaction.prepare_to_send()

            logger.debug("TX [%s] Persisted transaction", destination)
            logger.debug("TX [%s] Sending transaction...", destination)

            # Actually send the transaction
            code, response = yield self.transport_layer.send_transaction(
                transaction
            )

            logger.debug("TX [%s] Sent transaction", destination)
            logger.debug("TX [%s] Marking as delivered...", destination)

            yield transaction.delivered(code, response)

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
