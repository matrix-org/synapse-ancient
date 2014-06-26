# -*- coding: utf-8 -*-

"""The transport layer is responsible for both sending transactions to remote
home servers and receiving a variety of requests from other home servers.

Typically, this is done over HTTP (and all home servers are required to
support HTTP), however individual pairings of servers may decide to communicate
over a different (albeit still reliable) protocol.
"""

from twisted.internet import defer
from protocol.units import Transaction

import logging
import json
import re


logger = logging.getLogger("synapse.transport")


class TransportReceivedCallbacks(object):
    """ Callbacks used when we receive a transaction
    """
    def on_transaction(self, transaction):
        """ Called on PUT /send/<transaction_id>, or on response to a request
        that we sent (e.g. a pagination request)

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
    """ Callbacks used when someone want's data from us
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


class TransportLayer(object):
    """This is a basic implementation of the transport layer that translates
    transactions and other requests to/from HTTP.

    Attributes:
        server_name (str): Local home server host

        server (synapse.protocol.http.HttpServer): the http server to
                register listeners on

        client (synapse.protocol.http.HttpClient): the http client used to
                send requests

        request_callbacks (synapse.transport.TransportRequestCallbacks): The
                callback to fire when we receive requests for data.

        received_callbacks (synapse.transport.TransportReceivedCallbacks): The
                callback to fire when we receive data.
    """

    def __init__(self, server_name, server, client):
        """
        Args:
            server_name (str): Local home server host
            server (synapse.protocol.http.HttpServer): the http server to
                register listeners on
            client (synapse.protocol.http.HttpClient): the http client used to
                send requests
        """
        self.server_name = server_name
        self.server = server
        self.client = client
        self.request_callbacks = None
        self.received_callbacks = None

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

        path = "/state/%s/" % context

        yield self._trigger_transaction(destination, path, outlier=True)

    @defer.inlineCallbacks
    def trigger_get_pdu(self, destination, pdu_origin, pdu_id, outlier=False):
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

        path = "/pdu/%s/%s/" % (pdu_origin, pdu_id)

        yield self._trigger_transaction(destination, path, outlier=outlier)

    @defer.inlineCallbacks
    def send_transaction(self, transaction):
        """ Sends the given Transaction

        Args:
            transaction (synapse.protocol.units.Transaction): The transaction
                to send. The Transaction instance includes the destination to
                send it to.

        Returns:
            Deferred: Succeeds when we have finished processing the response
            of the request.

            The result of the deferred is a tuple in the form of
            (response_code, response_body) where the response_body is a
            python dict decoded from json
        """
        logger.debug("send_data dest=%s, txid=%s",
            transaction.destination, transaction.transaction_id)

        # We probably don't want to send things to ourselves, as that's just
        # going to confuse things when it comes to the IDs of both transactions
        # and PDUs
        if transaction.destination == self.server_name:
            raise RuntimeError("Transport layer cannot send to itself!")

        data = transaction.get_dict()

        # Actually send the transation to the remote home server.
        # This will throw if something toooo drastically goes wrong.
        code, response = yield self.client.put_json(
                transaction.destination,
                path="/send/%s/" % transaction.transaction_id,
                data=data
            )

        logger.debug("send_data dest=%s, txid=%s, got response: %d",
             transaction.destination, transaction.transaction_id, code)

        defer.returnValue((code, response))

    def register_received_callbacks(self, callback):
        """ Register a callback that will be fired when we receive data.

        Args:
            callback (synapse.transport.TransportReceivedCallbacks): The
                callback to fire when we receive data.

        Returns:
            None
        """
        self.received_callbacks = callback

        # This is when someone is trying to send us a bunch of data.
        self.server.register_path(
            "PUT",
            re.compile("^/send/([^/]*)/$"),
            lambda request, transaction_id:
                # We intercept this and decode the json a bit before
                # handing off to to the callbacks.
                self._on_send_request(request, transaction_id)
        )

    def register_request_callbacks(self, callback):
        """ Register a callback that will be fired when we get asked for data.

        Args:
            callback (synapse.transport.TransportRequestCallbacks): The
                callback to fire when we receive requests for data.

        Returns:
            None
        """
        self.request_callbacks = callback

        # This is for when someone asks us for everything since version X
        self.server.register_path(
            "GET",
            re.compile("^/pull/$"),
            lambda request:
                callback.on_pull_request(request.args["origin"][0],
                    request.args["v"])
        )

        # This is when someone asks for a data item for a given server
        # data_id pair.
        self.server.register_path(
            "GET",
            re.compile("^/pdu/([^/]*)/([^/]*)/$"),
            lambda request, pdu_origin, pdu_id:
                callback.on_pdu_request(pdu_origin, pdu_id)
        )

        # This is when someone asks for all data for a given context.
        self.server.register_path(
            "GET",
            re.compile("^/state/([^/]*)/$"),
            lambda request, context:
                callback.on_context_state_request(context)
        )

        self.server.register_path(
            "GET",
            re.compile("^/paginate/([^/]*)/$"),
            lambda request, context:
                self._on_paginate_request(context, request.args["v"],
                    request.args["limit"])
        )

    @defer.inlineCallbacks
    def _on_send_request(self, request, transaction_id):
        """ Called on PUT /send/<transaction_id>/
            We need to call on_transaction on callback, but we first
            want to decode the request to a TransportData

            Args:
                request (twisted.web.http.Request): The HTTP request.
                transaction_id (str): The transaction_id associated with this
                    request. This is *not* None.

            Returns:
                Deferred: Succeeds with a tuple of `(code, response)`, where
                `response` is a python dict to be converted into JSON that is
                used as the response body.
        """
        # Parse the request
        try:
            data = request.content.read()

            l = data[:20].encode("string_escape")
            logger.debug("Got data: \"%s\"" % l)

            transaction_data = json.loads(data)

            logger.debug("Decoded: %s" % (str(transaction_data)))

            # We should ideally be getting this from the security layer.
            # origin = body["origin"]

            # Add some extra data to the transaction dict that isn't included in
            # the request body.
            transaction_data.update(
                    transaction_id=transaction_id,
                    destination=self.server_name
                )

            transaction = Transaction.decode(transaction_data)

        except Exception as e:
            logger.exception(e)
            defer.returnValue(400, {"error": "Invalid transaction"})
            return

        logger.debug("Converted to transaction.")

        # OK, now tell the transaction layer about this bit of data.
        code, response = yield self.received_callbacks.on_transaction(
                transaction,
                "put_request")

        defer.returnValue((code, response))

    @defer.inlineCallbacks
    def _trigger_transaction(self, destination, path, outlier=False):
        """Used when we want to send a GET request to a remote home server
        that will result in them returning a response with a Transaction that
        we want to process.

        This will send a GET request to the `destination` home server and
        attempt to decode the response as a Transaction, if successful it will
        fire synapse.transport.TransportReceivedCallbacks

        Args:
            destination (str): The desteination home server to send the request
                to.
            path (str): The path to GET.
            outlier (bool): Should the returned PDUs be considered an outlier?
                Default: False

        Returns:
            Deferred: Succeeds when we have finished processing the repsonse.

        """

        # Get the JSON from the remote server
        data = yield self.client.get_json(
                destination,
                path=path
            )

        # Add certain keys to the JSON, ready for decoding as a Transaction
        data.update(
                    origin=destination,
                    destination=self.server_name,
                    transaction_id=None,
                )

        # We inform the layers above about the PDU as if we had received it
        # via a PUT.
        transaction = Transaction.decode(data, outlier=outlier)

        # We yield so that if the caller of this method want to wait for the
        # processing of the PDU to complete they can do so.
        yield self.received_callbacks.on_transaction(transaction)

    def _on_paginate_request(self, context, v_list, limits):
        if not limits:
            return defer.succeed(
                    (400, {"error": "Did not include limit param"})
                )

        limit = int(limits[-1])

        versions = [v.split(",", 1) for v in v_list]

        return self.request_callbacks.on_paginate_request(
            context, versions, limit)