# -*- coding: utf-8 -*-

from twisted.web.http import HTTPClient
from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientFactory
import json


class SynapseKeyClientError(Exception):
    pass


class SynapseKeyClientProtocol(HTTPClient):

    def connectionMade(self):
        self.sendCommand(b"GET", b"/key")
        self.endHeaders()

    def handleStatus(self, version, status, message):
        if status != b"200":
            self.factory.remote_key.errback(
                SynapseKeyClientError("Non 200 status", status, message)
            )

    def handleResponse(self, response_body_bytes):
        try:
            json_response = json.loads(response_body_bytes)
        except ValueError:
            self.factory.remote_key.errback(SynapseKeyClientError(
                "Invalid JSON response"))

        certificate = self.transport.getPeerCertificate()

        self.factory.remote_key.callback((json_response, certificate))

        self.transport.loseConnection()

    def connectionLost(self, reason):
        HTTPClient.connectionLost(self, reason)
        self.factory.remote_key.errback(
            SynapseKeyClientError("Connection lost", reason)
        )


@defer.inlineCallbacks
def fetch_server_key(server_name, ssl_context_factory):
    # TODO: Look up server_name using SRV records
    factory = ClientFactory()
    factory.protocol = SynapseKeyClientProtocol
    factory.remote_key = defer.Deferred()
    reactor.connectSSL(server_name, 8443, factory, ssl_context_factory)
    server_key, server_certificate = yield factory.remote_key
    defer.returnValue((server_key, server_certificate))
