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

def make_pdu(prev_pdus=[], **kwargs):
    """Provide some default fields for making a PduTuple."""
    pdu_fields = {
        "is_state":False,
        "unrecognized_keys":[],
        "outlier":False,
        "have_processed":True,
        "state_key":None,
        "power_level":None,
        "prev_state_id":None,
        "prev_state_origin":None,
    }
    pdu_fields.update(kwargs)

    return PduTuple(PduEntry(**pdu_fields), prev_pdus)

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
            make_pdu(
                pdu_id="the-pdu-id",
                origin="red",
                context="my-context",
                pdu_type="sy.topic",
                ts=123456789000,
                depth=1,
                is_state=True,
                content_json='{"topic":"The topic"}',
                state_key="",
                power_level=1000,
                prev_state_id="last-pdu-id",
                prev_state_origin="blue",
            ),
        ])

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/state/my-context/", None)
        self.assertEquals(200, code)
        self.assertEquals(1, len(response["pdus"]))

    @defer.inlineCallbacks
    def test_get_pdu(self):
        (code, response) = yield self.mock_http_server.trigger("GET",
                "/pdu/red/abc123def456/", None)
        self.assertEquals(404, code)

        # Now insert such a PDU
        self.mock_pdu_actions.mock_persisted_pdu(make_pdu(
            pdu_id="abc123def456",
            origin="red",
            context="my-context",
            pdu_type="sy.text",
            ts=123456789001,
            depth=1,
            content_json='{"text":"Here is the message"}',
        ))

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/pdu/red/abc123def456/", None)
        self.assertEquals(200, code)
        self.assertEquals(1, len(response["pdus"]))
        self.assertEquals("sy.text", response["pdus"][0]["pdu_type"])

class MockPduActions(object):
    def __init__(self):
        self.current_state_for = {}
        self.persisted_pdus = {}

    def mock_current_state(self, context, pdus):
        self.current_state_for[context] = pdus

    def current_state(self, context):
        if context not in self.current_state_for:
            return defer.succeed([])

        pdus = self.current_state_for[context]
        return defer.succeed([Pdu.from_pdu_tuple(p) for p in pdus])

    def mock_persisted_pdu(self, pdu):
        id = pdu.pdu_entry.pdu_id
        origin = pdu.pdu_entry.origin

        if origin not in self.persisted_pdus:
            self.persisted_pdus[origin] = {}

        self.persisted_pdus[origin][id] = pdu

    def get_persisted_pdu(self, pdu_id, pdu_origin):
        if pdu_origin not in self.persisted_pdus:
            pdu = None
        elif pdu_id not in self.persisted_pdus[pdu_origin]:
            pdu = None
        else:
            pdu = Pdu.from_pdu_tuple(self.persisted_pdus[pdu_origin][pdu_id])

        return defer.succeed(pdu)


class MockTransactionActions(object):
    pass
