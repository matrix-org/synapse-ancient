# trial imports
from twisted.internet import defer
from twisted.trial import unittest

# python imports
from mock import patch, Mock
import json
import os

from ..utils import MockHttpServer

from synapse.federation import initialize_http_federation
from synapse.federation.units import Pdu
from synapse.persistence.transactions import PduTuple

class FederationTestCase(unittest.TestCase):
    def setUp(self):
        # TODO: mock an HTTP client we can use
        self.mock_http_server = MockHttpServer()
        self.mock_pdu_actions = MockPduActions()
        self.mock_transaction_actions = MockTransactionActions()
        self.federation = initialize_http_federation(
                "test",
                http_server=self.mock_http_server,
                http_client=None,
                pdu_actions=self.mock_pdu_actions,
                transaction_actions=self.mock_transaction_actions
        )

    @defer.inlineCallbacks
    def test_get_state(self):
        # Empty context initially
        (code, response) = yield self.mock_http_server.trigger("GET",
                "/state/my-context/", None)
        self.assertEquals(200, code)
        self.assertFalse(response["pdus"])

class MockPduActions(object):
    def current_state(self, context):
        return defer.succeed([])

class MockTransactionActions(object):
    pass
