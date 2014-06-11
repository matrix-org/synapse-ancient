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


class LineReader(basic.LineReceiver):
    delimiter = '\n'

    def __init__(self, message_layer):
        self.message_layer = message_layer

    def connectionMade(self):
        self.transport.write('>>> ')

    def lineReceived(self, line):
        #self.sendLine('Echo: ' + line)
        try:
            if not line:
                return

            cmd, room_id, data = line.split(" ", 2)

            if cmd == "msg":
                sender, body = data.split(" ", 1)
                self.message_layer.send_message(sender, room_id, body)
                self.sendLine("OK")
            elif cmd == "partial":
                sender, receiver, body = data.split(" ", 2)
                self.message_layer.send_message_partial(
                    sender, room_id, body, receiver)
                self.sendLine("OK")
            elif cmd == "add":
                self.message_layer.send_join(room_id, data)
                self.sendLine("OK")
            elif cmd == "create":
                self.message_layer.send_join(room_id, data)
                self.sendLine("OK")
        except Exception as e:
            logging.exception(e)
        finally:
            self.transport.write('>>> ')

#stdio.StandardIO(LineReader(sServer))
