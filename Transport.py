# -*- coding: utf-8 -*-

from twisted.internet import defer

import logging
import json
import re


class TransportLayer(object):
    """ This layer is responsible for actually communicating with
        a remote home server.

        This is done by starting a HTTP server and listening for certain
        events, which trigger callbacks.
        This layer also contains a HTTP client for hitting out to remote
        home servers
    """

    def trigger_get_context_metadata(self, destination, context):
        """ Requests all metadata for a given context (i.e. room) from the
            given server
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Requests the pdu with give id and origin from the given server
        """
        pass

    def send_data(self, transport_data):
        """ Sends the given TransportData

            Returns a defered with tuple of (response_code, response_json_body)
        """
        pass

    def register_callbacks(self, callbacks):
        """ Register TransportCallbacks that will be fired when we receive
            data.
        """
        pass


class TransportCallbacks(object):
    """ Anything that uses the transport layer *must* handle these callbacks.
        These are fired when a remote home server is trying to communicate
        with us.
    """

    def on_pull_request(self, version):
        """ Called on GET /pull/<version>/

            Should return (as a deferred) a tuple of
            (response_code, response_body_json)
        """
        pass

    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/

            Should return (as a deferred) a tuple of
            (response_code, response_body_json)
        """
        pass

    def on_context_metadata_request(self, context):
        """ Called on GET /metadata/<context>/

            Should return (as a deferred) a tuple of
            (response_code, response_body_json)
        """
        pass

    def on_transport_data(self, transport_data):
        """ Called on PUT /send/<transaction_id>

            Should return (as a deferred) a tuple of
            (response_code, response_body_json)
        """
        pass


class TransportData(object):
    """ Used to represent some piece of data that we send/receive.
        These may or may not be associated with a transaction (e.g.,
        we may receive data from a GET request.)

        These are not persisted anywhere
    """
    def __init__(self, origin, destination, transaction_id, body):
        self.origin = origin
        self.destination = destination
        self.transaction_id = transaction_id
        self.body = body


# This layer is what we use to talk HTTP. We set up a HTTP server to listen
# for PUTs (people trying to send us data) and GETs (people trying to get
# missing data).
#
# This is the bottom layer of the Server-To-Server stack.

class SynapseHttpTransportLayer(TransportLayer):
    """ Used to talk HTTP, both as a client and server """

    def __init__(self, server_name, server, client):
        """ server_name: current server host and port
            server: instance of HttpWrapper.HttpServer to use
            client: instance of HttpWrapper.HttpClient to use
        """
        self.server_name = server_name
        self.server = server
        self.client = client
        self.callbacks = None

    def register_callbacks(self, callbacks):
        """ We register callbacks the required callbacks for the transport
            layer here.
        """

        logging.debug("register_callbacks")

        self.callbacks = callbacks

        # This is for when someone asks us for everything since version X
        self.server.register_path(
            "GET",
            re.compile("^/pull/([^/]*)/$"),
            lambda request, version:
                callbacks.on_pull_request(int(version))
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
            re.compile("^/metadata/([^/]*)/$"),
            lambda request, context:
                callbacks.on_context_metadata_request(context)
        )

        # This is when someone is trying to send us a bunch of data.
        self.server.register_path(
            "PUT",
            re.compile("^/send/([^/]*)/$"),
            lambda request, transaction_id:
                # We intercept this and decode the json a bit before
                # handing off to to the callbacks.
                self.on_send_request(request, transaction_id, callbacks)
        )

    @defer.inlineCallbacks
    def trigger_get_context_metadata(self, destination, context):
        """ Gets all the current metdata for a given room from the
            given server
        """

        logging.debug("trigger_get_context_metadata dest=%s, context=%s",
             (destination, context))

        body = yield self.client.get_json(
                destination,
                path="/metadata/%s/" % context
            )

        yield self.callbacks.on_transport_data(
                TransportData(
                    origin=destination,
                    destination=self.server_name,
                    transaction_id=None,
                    body=body
                )
            )

    @defer.inlineCallbacks
    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Gets a particular pdu by talking to the destination server
        """

        logging.debug("trigger_get_pdu dest=%s, pdu_origin=%s, pdu_id=%s",
             (destination, pdu_origin, pdu_id))

        body = yield self.client.get_json(
                destination,
                path="/message/%s/%s/" % (pdu_origin, pdu_id)
            )

        yield self.callbacks.on_transport_data(
                TransportData(
                    origin=destination,
                    destination=self.server_name,
                    transaction_id=None,
                    body=body
                )
            )

    @defer.inlineCallbacks
    def send_data(self, transport_data):
        """ Sends the specifed data, with the given transaction id, to the
            specified server using a HTTP PUT /send/<txid>/
        """

        logging.debug("send_data dest=%s, txid=%s",
             (transport_data.destination, transport_data.transaction_id))

        if transport_data.destination == self.server_name:
            raise RuntimeError("Transport layer cannot send to itself!")

        code, response = yield self.put_json(
                transport_data.destination,
                path="/send/%s/" % transport_data.transaction_id,
                data=transport_data.data
            )

        logging.debug("send_data dest=%s, txid=%s, got response: %d",
             (transport_data.destination, transport_data.transaction_id, code))

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

            body = json.loads(data)
        except Exception as e:
            logging.exception(e)
            return (400, {"error": "Invalid json"})

        # OK, now tell the transaction layer about this bit of data.
        code, response = yield callback.on_transport_data(
                TransportData(
                    origin=body["origin"],
                    destination=self.server_name,
                    transaction_id=transaction_id,
                    body=body
                )
            )

        defer.returnValue((code, response))
