# -*- coding: utf-8 -*-

from twisted.internet import defer

from Transport import TransportCallbacks, TransportData

from db.transaction import Transaction

import logging
import time


class PduDecodeException(Exception):
    pass


class TransactionLayer(TransportCallbacks):
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

    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            The order is an integer which defines the order in which pdus
            will be sent (ones with a larger order come later). This is to
            make sure we maintain the ordering defined by the versions without
            having to know what the versions look like at this layer.

            pdu_json is a python dict that can be converted into json.

            Returns a deferred which returns when the pdu has successfully
            been sent to the destination.
        """
        pass

    def trigger_get_context_state(self, destination, context):
        """ Try and get the remote home server to give us all state about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass

    @staticmethod
    def from_transport_data(transport_data):
        """ Converts TransportData into a Transaction instance
        """

        return Transaction(
                transaction_id=transport_data.transaction_id,
                origin=transport_data.origin,
                pdu_list=transport_data.body["data"],
                ts=transport_data.body["ts"]
            )

    @staticmethod
    def to_transport_data(transaction):
        """ Converts a Transaction into a TransportData
        """

        return TransportData(
               origin=transaction.origin,
               destination=transaction.destination,
               transaction_id=transaction.transaction_id,
               body={
                       "origin": transaction.origin,
                       "data": transaction.pdu_list,
                       "ts": transaction.ts
                   }
           )


class TransactionCallbacks(object):
    """ When the transaction layer receives requests it can't process, we
        send them upwards via these set's of callbacks.
    """

    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Get's called when we want to get a specific pdu
            Returns a dict representing the pdu
        """
        pass

    def on_get_context_state(self, context):
        """ Get's called when we want to get all metadata pdus for a given
            context.
            Returns a list of dicts.
        """
        pass

    def on_received_pdu(self, origin, sent_ts, pdu_json):
        """ Get's called when we receive a pdu via a transaction.

            Returns a deferred which is called back when it has been
            successfully processed *and* persisted, or errbacks with either
            a) PduDecodeException, at which point we return a 400 on the
            entire transaction, or b) another exception at which point we
            respond with a 500 to the entire transaction.
        """
        pass


class HttpTransactionLayer(TransactionLayer):
    def __init__(self, server_name, transport_layer):
        self.server_name = server_name

        self.transport_layer = transport_layer
        self.transport_layer.register_callbacks(self)

        self.data_layer = None

        # Responsible for batching pdus
        self._transaction_queue = _TransactionQueue(
                server_name,
                transport_layer
            )

    def set_data_layer(self, data_layer):
        self.data_layer = data_layer

    @defer.inlineCallbacks
    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferred
        """
        yield self._transaction_queue.enqueue_pdu(destination, pdu_json, order)

    @defer.inlineCallbacks
    def on_pull_request(self, version):
        """ Called on GET /pull/<version>/ from transport layer
        """
        response = yield self._get_sent_versions(version)
        data = self._wrap_data(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        response = yield self.data_layer.on_data_request(pdu_origin, pdu_id)
        if response:
            data = self._wrap_data([])
        else:
            data = self._wrap_data([response])

        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_context_state_request(self, context):
        """ Called on GET /state/<context>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        response = yield self.data_layer.on_get_context_state(context)
        data = self._wrap_data(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_transport_data(self, transport_data):
        """ Called on PUT /send/<transaction_id> from transport layer
        """
        transaction_id = transport_data.transaction_id

        # Check to see if we a) have a transaction_id associated with this
        # request and if so b) have we already responded to it?
        if transaction_id:
            transaction_results = yield Transaction.findBy(
                txid=transaction_id, origin=transport_data.origin
            )

            if transaction_results:
                # We know about this transaction. Have we responded?
                for t in transaction_results:
                    if t.response_code > 0 and t.response:
                        defer.returnValue(
                            (t.response_code, t.response)
                        )
                        return

        transaction = self.from_transport_data(
                transport_data
            )

        # Pass request to transaction layer.
        try:
            code, response = yield self.data_layer.on_received_transaction(
                    transaction
                )

            transaction.response = response
            transaction.respone_code = code

            yield transaction.save()
        except Exception as e:
            logging.exception(e)

            # transaction.response = {"error": "Internal server error"}
            # transaction.respone_code = 500

            # yield transaction.save()

            defer.returnValue((500, {"error": "Internal server error"}))
            return

        defer.returnValue((transaction.respone_code, transaction.response))

    def trigger_get_context_state(self, destination, context):
        """ Try and get the remote home server to give us all state about
            a given context
        """
        return self.transport_layer.trigger_get_context_state(
            destination, context)

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        return self.transport_layer.trigger_get_data(
            destination, pdu_origin, pdu_id)


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

    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferred
        """
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        deferred = defer.Deferred()
        self.pending_pdus_list.setdefault(destination, []).append(
                    (pdu_json, deferred, order)
                )

        self._attempt_new_transaction(destination)

        return deferred

    @defer.inlineCallbacks
    def _attempt_new_transaction(self, destination):
        if destination in self.pending_transactions:
            return

        # tuple_list is a list of (pending_pdu, deferred, order)
        tuple_list = self.pending_pdus_list.get(destination)

        if not tuple_list:
            return

        # Sort based on the order field
        tuple_list.sort(key=lambda t: t[2])

        transaction = Transaction.create(
                        ts=int(time.time() * 1000),
                        origin=self.server_name,
                        destination=destination,
                        pdu_list=[p[0] for p in tuple_list]
                    )

        code, response = yield self.transport_layer.send_data(
                TransactionLayer.to_transport_data(transaction)
            )

        if code == 200:
            for _, deferred, _ in tuple_list:
                deferred.callback(None)

                # Ensures we don't continue until all callbacks on that
                # deferred have fired
                yield deferred

        # At this point we know the layer above has been notified of all the
        # pdus that have successfully been sent.
        # This means that it safe to mark the transaction as sent. Otherwise
        # if we died between marking the transaction as sent and the layers
        # above persisting this, they would never get told that it was
        # successfully sent.

        transaction.respone_code = code
        transaction.response = response

        defer.returnValue((code, response))

        yield transaction.save()

        del self.pending_transactions[destination]

        # Check to see if there is anything else to send.
        self._attempt_new_transaction(self, destination)