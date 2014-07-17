# trial imports
from twisted.internet import defer
from twisted.trial import unittest

# python imports
from mock import patch, Mock
import json
import os

from ..utils import MockHttpServer

from synapse.federation import initialize_http_federation
from synapse.persistence.transactions import PduTuple, PduEntry

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
        self.mock_persistence = Mock(spec=[
            "get_current_state_for_context",
            "get_pdu",
        ])
        self.federation = initialize_http_federation(
                "test",
                http_server=self.mock_http_server,
                http_client=None,
                persistence_service=self.mock_persistence
        )

    @defer.inlineCallbacks
    def test_get_state(self):
        self.mock_persistence.get_current_state_for_context.return_value = (
            defer.succeed([])
        )

        # Empty context initially
        (code, response) = yield self.mock_http_server.trigger("GET",
                "/state/my-context/", None)
        self.assertEquals(200, code)
        self.assertFalse(response["pdus"])

        # Now lets give the context some state
        self.mock_persistence.get_current_state_for_context.return_value = (
            defer.succeed([
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
        )

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/state/my-context/", None)
        self.assertEquals(200, code)
        self.assertEquals(1, len(response["pdus"]))

    @defer.inlineCallbacks
    def test_get_pdu(self):
        self.mock_persistence.get_pdu.return_value = (
            defer.succeed(None)
        )

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/pdu/red/abc123def456/", None)
        self.assertEquals(404, code)

        # Now insert such a PDU
        self.mock_persistence.get_pdu.return_value = (
            defer.succeed(
                make_pdu(
                    pdu_id="abc123def456",
                    origin="red",
                    context="my-context",
                    pdu_type="sy.text",
                    ts=123456789001,
                    depth=1,
                    content_json='{"text":"Here is the message"}',
                )
            )
        )

        (code, response) = yield self.mock_http_server.trigger("GET",
                "/pdu/red/abc123def456/", None)
        self.assertEquals(200, code)
        self.assertEquals(1, len(response["pdus"]))
        self.assertEquals("sy.text", response["pdus"][0]["pdu_type"])
