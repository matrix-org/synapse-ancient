# -*- coding: utf-8 -*-

from twisted.internet import defer

from transport import TransportReceivedCallbacks, TransportRequestCallbacks
from protocol.units import Transaction, Pdu
from persistence.transaction import (LastSentTransactionDbEntry,
    TransactionToPduDbEntry)

import logging
import time


class PduDecodeException(Exception):
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
    """

    def enqueue_pdu(self, pdu, order):
        """ Schedules the pdu to be sent.

            The order is an integer which defines the order in which pdus
            will be sent (ones with a larger order come later). This is to
            make sure we maintain the ordering defined by the versions without
            having to know what the versions look like at this layer.

            Returns a deferred which returns when the pdu has successfully
            been sent to the destination.
        """
        pass


class TransactionCallbacks(object):
    """ Get's called when the transaction layer receives new data.
    """

    def on_received_pdus(self, pdu_list):
        """ Get's called when we receive a pdus via a transaction.

            Returns a deferred which is called back when they have been
            successfully processed *and* persisted, or errbacks with either
            a) PduDecodeException, at which point we return a 400 on the
            entire transaction, or b) another exception at which point we
            respond with a 500 to the entire transaction.
        """
        pass

    def on_context_state_request(self, context):
        """ Called on GET /state/<context>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        pass

    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        pass


class HttpTransactionLayer(TransactionLayer):
    def __init__(self, server_name, transport_layer):
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
            self._transaction_queue.enqueue_pdu(pdu, order)

    def _wrap_pdus(self, pdu_list):
        return Transaction(
                pdus=pdu_list,
                origin=self.server_name,
                ts=int(time.time() * 1000)
            ).get_dict()

    def set_callback(self, callback):
        self.callback = callback

    @defer.inlineCallbacks
    def on_pull_request(self, origin, versions):
        """ Called on GET /pull/ from transport layer
        """

        # We know that we're the only node, so we assume that they're
        # integers and thus can just take the max
        tx_id = max([int(v) for v in versions])

        response = yield Pdu.after_transaction(
                self.server_name,
                tx_id,
                origin
            )

        if not response:
            response = []

        data = self._wrap_pdus(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer
            Returns a deferred tuple of (code, response)
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
        """
        response = yield self.callback.on_context_state_request(context)

        data = self._wrap_pdus(response)

        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_transaction(self, transaction):
        """ Called on PUT /send/<transaction_id> from transport layer
        """

        logging.debug("[%s] Got transaction", transaction.transaction_id)

        # Check to see if we a) have a transaction_id associated with this
        # request and if so b) have we already responded to it?
        db_entry = yield transaction.get_db_entry()
        response = yield db_entry.have_responded()

        if response:
            logging.debug("[%s] We've already responed to this request",
                transaction.transaction_id)
            defer.returnValue(response)
            return

        logging.debug("[%s] Transacition is new", transaction.transaction_id)

        # Pass request to transaction layer.
        try:
            code, response = yield self.callback.on_received_pdus(
                    transaction.pdus
                )
        except PduDecodeException as e:
            # Problem decoding one of the PDUs, BAIL BAIL BAIL
            logging.exception(e)
            code = 400
            response = {"error": str(e)}
        except Exception as e:
            logging.exception(e)

            # We don't save a 500 response!

            defer.returnValue((500, {"error": "Internal server error"}))
            return

        yield db_entry.set_response(code, response)
        defer.returnValue((code, response))


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

    def enqueue_pdu(self, pdu, order):
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        deferred_list = []

        for destination in pdu.destinations:
            deferred = defer.Deferred()
            self.pending_pdus_list.setdefault(destination, []).append(
                        (pdu, deferred, order)
                    )

            self._attempt_new_transaction(destination)

            deferred_list.append(deferred)

        return defer.DeferredList(deferred_list)

    @defer.inlineCallbacks
    def _attempt_new_transaction(self, destination):
        if destination in self.pending_transactions:
            return

        # tuple_list is a list of (pending_pdu, deferred, order)
        tuple_list = self.pending_pdus_list.pop(destination, None)

        if not tuple_list:
            return

        try:
            # Sort based on the order field
            tuple_list.sort(key=lambda t: t[2])

            last_sent_rows = yield LastSentTransactionDbEntry.findBy(
                    destination=destination
                )

            if last_sent_rows:
                prev_txs = [r.transaction_id for r in last_sent_rows]
            else:
                prev_txs = []

            transaction = Transaction.create_new(
                            origin=self.server_name,
                            destination=destination,
                            pdus=[p[0] for p in tuple_list],
                            previous_ids=prev_txs
                        )

            # Update the transaction_id -> pdu_id table
            yield defer.DeferredList([TransactionToPduDbEntry(
                    transaction_id=transaction.transaction_id,
                    destination=destination,
                    pdu_id=p.pdu_id
                ).save() for p in transaction.pdus])

            # Actually send the transaction
            code, response = yield self.transport_layer.send_transaction(
                    transaction
                )

            # Okay, we successfully talked to the server (we didn't throw an
            # error),  so update the last_sent_transactions table
            yield defer.DeferredList([row.delete() for row in last_sent_rows])
            yield LastSentTransactionDbEntry(
                    transaction_id=transaction.transaction_id,
                    destination=destination,
                    ts=transaction.ts
                ).save()

            for _, deferred, _ in tuple_list:
                if code == 200:
                    deferred.callback(None)
                else:
                    deferred.errback(RuntimeError("Got status %d" % code))

                # Ensures we don't continue until all callbacks on that
                # deferred have fired
                yield deferred

        finally:
            # We want to be *very* sure we delete this after we stop processing
            self.pending_transactions.pop(destination, None)

            # Check to see if there is anything else to send.
            self._attempt_new_transaction(destination)