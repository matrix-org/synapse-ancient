# -*- coding: utf-8 -*-

from twisted.internet import defer

from twisted.trial import unittest
from ..transaction import HttpTransactionLayer
from ..transport import TransportLayer

from twisted.enterprise import adbapi
from twistar.registry import Registry

class TransportTestCase(unittest.TestCase):
    def setUp(self):
        Registry.DBPOOL = adbapi.ConnectionPool('sqlite3', db=":memory:")
        pass

    def test_enqueue_pdu_single(self):
        """ Test to make sure that enqueue_pdu correctly hit's the transport layer
        """
        # destination, pdu_json, order

        test_server_name = "test_server"
        test_destination = "test_destination"
        test_pdu_json = {}
        test_order = 5

        test_case = self

        self.pdu_fired = False

        test_r_code = 200
        test_response= {}

        class TestTransportLayer(TransportLayer):
            def trigger_get_context_metadata(self, destination, context):
                test_case.fail()

            def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
                test_case.fail()

            def send_data(self, transport_data):
                test_case.assertEqual(transport_data.destination, test_destination)
                test_case.pdu_fired = True
                return defer.succeed( (test_r_code, test_response) )

            def register_callbacks(self, callbacks):
                #test_case.fail()
                pass

        transport_layer = TestTransportLayer()

        transaction_layer = HttpTransactionLayer(
                             test_server_name,
                             transport_layer
                         )

        d = transaction_layer.enqueue_pdu(test_destination, test_pdu_json, test_order)

        d.addCallback(lambda x: self.assertTrue(self.pdu_fired))

        return d


    def test_trigger_get_context_state(self):
        """ Make sure we trigger the correct callback on the transport layer
        """
        test_server_name = "test_server"
        test_destination = "test_destination"
        test_context = "test_context"

        test_case = self

        self.test_context_state_fired = False

        class TestTransportLayer(TransportLayer):
            def trigger_get_context_state(self, destination, context):
                test_case.assertEqual(destination, test_destination)
                test_case.assertEqual(context, test_context)
                test_case.test_context_state_fired = True
                return defer.succeed( None )

            def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
                test_case.fail()

            def send_data(self, transport_data):
                test_case.fail()

            def register_callbacks(self, callbacks):
                #test_case.fail()
                pass

        transport_layer = TestTransportLayer()

        transaction_layer = HttpTransactionLayer(
                             test_server_name,
                             transport_layer
                         )

        d = transaction_layer.trigger_get_context_state(test_destination, test_context)

        d.addCallback(lambda x: self.assertTrue(self.test_context_state_fired))

        return d