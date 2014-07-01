import re

from synapse.messaging import MessagingCallbacks

class SynapseHomeServer(MessagingCallbacks):
    def __init__(self, http_server, server_name, messaging_layer):
        self.server_name = server_name
        self.http_server = http_server
        self.messaging_layer = messaging_layer
        self.messaging_layer.set_callback(self)

        self.http_server.register_path(
                "PUT", re.compile("^/events/([^/]*)$"), self._on_PUT)

        self.http_server.register_path(
                "GET", re.compile("^/events$"), self._on_GET)

    def on_receive_pdu(self, pdu):
        pdu_type = pdu.pdu_type
        print "#%s (receive) *** %s" % (pdu.context, pdu_type)

    def on_state_change(self, pdu):
        print "#%s (state) %s *** %s" % (pdu.context, pdu.state_key, pdu.pdu_type)

    def _on_PUT(self, request, event_id):
        print "PUT Req %s Event %s" % (request, event_id)

    def _on_GET(self, request):
        print "GET Req %s" % request
            
