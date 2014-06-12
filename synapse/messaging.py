from twisted.protocols import basic

from pdu import PduCallbacks

import logging


class MessagingCallbacks(object):
    def on_receive_pdu(self, pdu):
        pass


class Messaging(PduCallbacks):
    def send_pdu(self, pdu):
        pass

    def get_context_state(self, destination, context):
        pass


class MessagingImpl(Messaging):
    """ This is (for now) simply providing a nice interface for people who want
    to use the server to server stuff.
    """
    def __init__(self, server_name, transport_layer, transaction_layer,
        pdu_layer, callback=None):
        self.transport_layer = transport_layer
        self.transaction_layer = transaction_layer
        self.pdu_layer = pdu_layer
        self.server_name = server_name
        self.callback = callback

        self.pdu_layer.set_callback(self)

    def set_callback(self, callback):
        self.callback = callback

    def on_receive_pdu(self, pdu):
        return self.callback.on_receive_pdu(pdu)

    def on_unseen_pdu(self, originating_server, pdu_id, origin):
        return self.transport_layer.trigger_get_pdu(
            originating_server, pdu_id, origin)

    def send_pdu(self, pdu):
        return self.pdu_layer.send_pdu(pdu)

    def get_context_state(self, destination, context):
        return self.transport_layer.trigger_get_context_state(destination,
            context)
