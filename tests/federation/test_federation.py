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
from synapse.persistence.transactions import PduTuple, PduEntry
from synapse.persistence.tables import PdusTable

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

        # Now lets give the context some state
        self.mock_pdu_actions.mock_current_state("my-context", [
            PduTuple(PduEntry(
                pdu_id="the-pdu-id",
                origin="red",
                context="my-context",
                pdu_type="sy.topic",
                ts=123456789000,
                depth=1,
                is_state=True,
                content_json='{"topic":"The topic"}',
                unrecognized_keys=[],
                outlier=False,
                have_processed=True,
                state_key="",
                power_level=1000,
                prev_state_id="last-pdu-id",
                prev_state_origin="blue",
            ), []),
        ])

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/state/my-context/", None)
        self.assertEquals(200, code)
        self.assertEquals(len(response["pdus"]), 1)

class MockPduActions(object):
    def __init__(self):
        self.current_state_for = {}

    def mock_current_state(self, context, pdus):
        self.current_state_for[context] = pdus

    def current_state(self, context):
        if context not in self.current_state_for:
            return defer.succeed([])

        pdus = self.current_state_for[context]
        return defer.succeed([Pdu.from_pdu_tuple(p) for p in pdus])

class MockTransactionActions(object):
    pass
