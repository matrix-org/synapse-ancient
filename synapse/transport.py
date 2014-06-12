# -*- coding: utf-8 -*-

"""The transport layer is responsible for both sending transactions to remote
home servers and receiving a variety of requests from other home servers.
Typically, this is done over HTTP and all home servers are required to
support HTTP, however individual pairings of servers may decide to communicate
over a different (albeit still reliable) protocol.
"""

from twisted.internet import defer
from protocol.units import Transaction

import logging
import json
import re


class TransportLayer(object):
    """This is a basic interface that any transport layer should support. For
    the most part, these roughly map to requests that will be sent to the
    destination home server.
    """

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
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Requests the pdu with give id and origin from the given server.

        This will *not* return the PDU, but will pass the received state
        to the TransportReceivedCallbacks.on_transaction callback in the same
        way as if it had been sent them in a Transaction.

        Args:
            destination (str): The host name of the remote home server we want
                to get the state from.
            pdu_origin (str): The home server which created the PDU.
            pdu_id (str): The id of the PDU being requested

        Returns:
            Deferred: Succeeds when we have finished processing the
            response of the request.

            The argument passed to the deferred is undefined and may be None.
        """
        pass

    def send_transaction(self, transaction):
        """ Sends the given Transaction

        Args:
            transaction (synapse.protocol.units.Transaction): The transaction
                to send. The Transaction instance includes the destination to
                send it to.

        Returns:
            Deferred: Succeeds when we have finished processing the response
            of the request.

            The argument passed to the callback is a tuple in the form of
            (response_code, response_body) where the response_body is a
            python dict decoded from json
        """
        pass

    def register_received_callbacks(self, callback):
        """ Register a callback that will be fired when we receive data.

        Args:
            callback (synapse.transport.TransportReceivedCallbacks): The
                callback to fire when we receive data.

        Returns:
            None
        """
        pass

    def register_request_callbacks(self, callback):
        """ Register a callback that will be fired when we get asked for data.

        Args:
            callback (synapse.transport.TransportRequestCallbacks): The
                callback to fire when we receive requests for data.

        Returns:
            None
        """
        pass


class TransportReceivedCallbacks(object):
    """ Get's called when we receive a transaction
    """
    def on_transaction(self, transaction):
        """ Called on PUT /send/<transaction_id>

        Args:
            transaction (synapse.transaction.Transaction): The transaction that
                was sent to us.

        Returns:
            twisted.internet.defer.Deferred: A deferred that get's fired when
            the transaction has finished being processed.

            The result should be a tuple in the form of
            `(response_code, respond_body)`, where `response_body` is a python
            dict that will get serialized to JSON.

            On errors, the dict should have an `error` key with a brief message
            of what went wrong.
        """
        pass


class TransportRequestCallbacks(object):
    """ Get's called when someone want's data from us
    """
    def on_pull_request(self, versions):
        """ Called on GET /pull/?v=...

        This is hit when a remote home server wants to received all data
        after a given transaction. This is used when a home server comes back
        online and wants to get everything it has missed.

        Args:
            versions (list): A list of transaction_ids that should be used to
                determine what PDUs the remote side have not yet seen.

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

    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/

        Someone wants a particular PDU. This PDU may or may not have originated
        from us.

        Args:
            pdu_origin (str): The home server that generated the PDU
            pdu_id (str): The id that the origination home server assigned it.

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

    def on_context_state_request(self, context):
        """ Called on GET /state/<context>/

        Get's hit when someone wants all the *current* state for a given
        contexts.

        Args:
            context (str): The name of the context that we're interested in.

        Returns:
            twisted.internet.defer.Deferred: A deferred that get's fired when
            the transaction has finished being processed.

            The result should be a tuple in the form of
            `(response_code, respond_body)`, where `response_body` is a python
            dict that will get serialized to JSON.

            On errors, the dict should have an `error` key with a brief message
            of what went wrong.
        """
        pass


class HttpTransportLayer(TransportLayer):
    """ Used to talk HTTP, both as a client and server """

    def __init__(self, server_name, server, client):
        """ server_name: current server host and port
            server: instance of HttpWrapper.HttpServer to use
            client: instance of HttpWrapper.HttpClient to use
        """
        self.server_name = server_name
        self.server = server
        self.client = client
        self.request_callbacks = None
        self.received_callbacks = None

    def register_request_callbacks(self, callbacks):
        self.request_callbacks = callbacks

        # This is for when someone asks us for everything since version X
        self.server.register_path(
            "GET",
            re.compile("^/pull/$"),
            lambda request:
                callbacks.on_pull_request(request.args["origin"][0],
                    request.args["v"])
        )

        # This is when someone asks for a data item for a given server
        # data_id pair.
        self.server.register_path(
            "GET",
            re.compile("^/pdu/([^/]*)/([^/]*)/$"),
            lambda request, pdu_origin, pdu_id:
                callbacks.on_pdu_request(pdu_origin, pdu_id)
        )

        # This is when someone asks for all data for a given context.
        self.server.register_path(
            "GET",
            re.compile("^/state/([^/]*)/$"),
            lambda request, context:
                callbacks.on_context_state_request(context)
        )

    def register_received_callbacks(self, callbacks):
        self.received_callbacks = callbacks

        # This is when someone is trying to send us a bunch of data.
        self.server.register_path(
            "PUT",
            re.compile("^/send/([^/]*)/$"),
            lambda request, transaction_id:
                # We intercept this and decode the json a bit before
                # handing off to to the callbacks.
                self._on_send_request(request, transaction_id, callbacks)
        )

    @defer.inlineCallbacks
    def trigger_get_context_state(self, destination, context):
        """ Gets all the current state for a given room from the
            given server
        """

        logging.debug("trigger_get_context_metadata dest=%s, context=%s",
             destination, context)

        data = yield self.client.get_json(
                destination,
                path="/state/%s/" % context
            )

        data.update(origin=destination,
                    destination=self.server_name,
                    transaction_id=None,
                )

        yield self.received_callbacks.on_transaction(
                Transaction.decode(data)
            )

    @defer.inlineCallbacks
    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Gets a particular pdu by talking to the destination server
        """

        logging.debug("trigger_get_pdu dest=%s, pdu_origin=%s, pdu_id=%s",
             destination, pdu_origin, pdu_id)

        data = yield self.client.get_json(
                destination,
                path="/pdu/%s/%s/" % (pdu_origin, pdu_id)
            )

        data.update(
                    origin=destination,
                    destination=self.server_name,
                    transaction_id=None,
                )

        yield self.received_callbacks.on_transaction(
                Transaction.decode(data)
            )

    @defer.inlineCallbacks
    def send_transaction(self, transaction):
        """ Sends the specifed data, with the given transaction id, to the
            specified server using a HTTP PUT /send/<txid>/
        """

        logging.debug("send_data dest=%s, txid=%s",
            transaction.destination, transaction.transaction_id)

        if transaction.destination == self.server_name:
            raise RuntimeError("Transport layer cannot send to itself!")

        code, response = yield self.client.put_json(
                transaction.destination,
                path="/send/%s/" % transaction.transaction_id,
                data=transaction.get_dict()
            )

        logging.debug("send_data dest=%s, txid=%s, got response: %d",
             transaction.destination, transaction.transaction_id, code)

        defer.returnValue((code, response))

    @defer.inlineCallbacks
    def _on_send_request(self, request, transaction_id, callback):
        """ Called on PUT /send/<transaction_id>/
            We need to call on_transport_data on callback, but we first
            want to decode the request to a TransportData
        """
        # Parse the request
        try:
            data = request.content.read()

            transaction_data = json.loads(data)
        except Exception as e:
            logging.exception(e)
            defer.returnValue(400, {"error": "Invalid json"})
            return

        # We should ideally be getting this from the security layer.
        # origin = body["origin"]

        transaction_data["transaction_id"] = transaction_id
        transaction_data["destination"] = self.server_name

        # OK, now tell the transaction layer about this bit of data.
        code, response = yield callback.on_transaction(
                Transaction.decode(transaction_data)
            )

        defer.returnValue((code, response))
