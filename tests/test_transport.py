# -*- coding: utf-8 -*-

from twisted.internet import defer

from twisted.trial import unittest
from transport import (SynapseHttpTransportLayer,
    TransportRequestCallbacks, TransportReceivedCallbacks)
from HttpWrapper import HttpClient, HttpServer
from protocol.units import Transaction, Pdu


class TransportTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test_send_data(self):
        """ Test that the transport data get's correctly converted into a HTTP
            request
        """
        test_destination = "test_destination"
        test_transaction_id = "12345"
        test_content = {"test": "test1"}

        expected_response_code = 200
        expected_response = {"test_response": "test"}

        test_case = self

        class TestHttpClient(HttpClient):
            def put_json(self, destination, path, data):
                test_case.assertEqual(destination, test_destination)
                test_case.assertEqual(path, "/send/%s/" % test_transaction_id)
                #test_case.assertEqual(data, test_body)
                t = Transaction.decode(data)

                return defer.succeed(
                        (expected_response_code, expected_response)
                    )

            def get_json(self, destination, path):
                test_case.fail()

        transport_layer = SynapseHttpTransportLayer(
                "test_server",
                client=TestHttpClient(),
                server=None
            )

        pdus = [Pdu(pdu_id="as", origin="test_server", content=test_content)]
        data = Transaction.create_new(
                origin="test_server",
                destination=test_destination,
                pdus=pdus,
                transaction_id=test_transaction_id
            )

        d = transport_layer.send_transaction(data)

        d.addCallback(
                self.assertEqual,
                (expected_response_code, expected_response)
            )

        return d

    def test_trigger_get_context_state(self):
        """ Test that when we want to get state for a given context, this
            triggers both the correct GET request and hits the correct
            callback with the result
        """
        test_local_server = "test_server"
        test_destination = "test_destination"
        test_context = "test_context"

        test_case = self

        test_return_data = {"return_data": "data"}

        class TestTransportCallbacks(TransportCallbacks):
            def on_pull_request(self, version):
                test_case.fail()

            def on_pdu_request(self, pdu_origin, pdu_id):
                test_case.fail()

            def on_context_state_request(self, context):
                test_case.fail()

            def on_transport_data(self, transport_data):
                test_case.assertEqual(transport_data.origin, test_destination)
                test_case.assertEqual(transport_data.destination,
                    test_local_server)
                test_case.assertEqual(transport_data.body, test_return_data)

        test_callbacks = TestTransportCallbacks()

        class TestHttpClient(HttpClient):
            def put_json(self, destination, path, data):
                test_case.fail()

            def get_json(self, destination, path):
                test_case.assertEqual(destination, test_destination)
                test_case.assertEqual(path, "/state/%s/" % test_context)

                return defer.succeed(test_return_data)

        class TestHttpServer(HttpServer):
            def register_path(self, method, path_pattern, callback):
                pass

        transport_layer = SynapseHttpTransportLayer(
                test_local_server,
                client=TestHttpClient(),
                server=TestHttpServer()
            )

        transport_layer.register_callbacks(test_callbacks)

        d = transport_layer.trigger_get_context_state(
            test_destination, test_context)

        return d

    def test_trigger_get_pdu(self):
        """ Test that when we want to get a specific, this triggers
            both the correct GET request and hits the correct callback with
            the result
        """
        test_local_server = "test_server"
        test_destination = "test_destination"
        test_pdu_origin = "test_pdu_origin"
        test_pdu_id = "test_pdu_id"

        test_case = self

        test_return_data = {"return_data": "data"}

        class TestTransportCallbacks(TransportCallbacks):
            def on_pull_request(self, version):
                test_case.fail()

            def on_pdu_request(self, pdu_origin, pdu_id):
                test_case.fail()

            def on_context_state_request(self, context):
                test_case.fail()

            def on_transport_data(self, transport_data):
                test_case.assertEqual(transport_data.origin, test_destination)
                test_case.assertEqual(transport_data.destination,
                    test_local_server)
                test_case.assertEqual(transport_data.body, test_return_data)

        test_callbacks = TestTransportCallbacks()

        class TestHttpClient(HttpClient):
            def put_json(self, destination, path, data):
                test_case.fail()

            def get_json(self, destination, path):
                test_case.assertEqual(destination, test_destination)
                test_case.assertEqual(path,
                    "/pdu/%s/%s/" % (test_pdu_origin, test_pdu_id))

                return defer.succeed(test_return_data)

        class TestHttpServer(HttpServer):
            def register_path(self, method, path_pattern, callback):
                pass

        transport_layer = SynapseHttpTransportLayer(
                test_local_server,
                client=TestHttpClient(),
                server=TestHttpServer()
            )

        transport_layer.register_callbacks(test_callbacks)

        d = transport_layer.trigger_get_pdu(test_destination, test_pdu_origin,
            test_pdu_id)

        return d

    def test_register_callbacks(self):
        """ Tests that we register for the correct callbacks
        """
        test_local_server = "test_server"

        # These are the list of acceptable registers as (method, example url)
        # As we register these we remove it from the list, so we expect it to be
        # empty by the time we finish registering
        test_paths = [
                      ("GET", "/pull/1234a/"),
                      ("GET", "/pdu/1234a/5678b/"),
                      ("GET", "/state/1234a/"),
                      ("PUT", "/send/1234a/")
                  ]

        test_case = self

        class TestHttpServer(HttpServer):
            def register_path(self, method, path_pattern, callback):
                for t in test_paths:
                    if t[0] == method and path_pattern.match(t[1]):
                        test_paths.remove(t)
                        return

                test_case.fail("Unrecognized register: %s, %s"
                    % (method, path_pattern.pattern))

        transport_layer = SynapseHttpTransportLayer(
                test_local_server,
                client=HttpClient(),
                server=TestHttpServer()
            )

        transport_layer.register_callbacks(TransportCallbacks())

        # Check we saw all of them
        self.assertEqual(len(test_paths), 0)

        return