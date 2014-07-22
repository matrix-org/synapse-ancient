# -*- coding: utf-8 -*-

from twisted.web.http import HTTPClient
from twisted.internet import defer, reactor
from twisted.internet.protocol import ClientFactory
import json


@defer.inlineCallbacks
def fetch_server_key(server_name, ssl_context_factory):
    """Fetch the keys for a remote server."""
    # TODO: Look up server_name using SRV records
    factory = ClientFactory()
    factory.protocol = SynapseKeyClientProtocol
    factory.remote_key = defer.Deferred()
    reactor.connectSSL(server_name, 8443, factory, ssl_context_factory)
    server_key, server_certificate = yield factory.remote_key
    defer.returnValue((server_key, server_certificate))


class SynapseKeyClientError(Exception):
    """The key wasn't retireved from the remote server.'"""
    pass


class SynapseKeyClientProtocol(HTTPClient):
    """Low level HTTPS client which retrieves an application/json response from
    the server and extracts the X.509 certificate for the remote peer from the
    SSL connection."""

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

