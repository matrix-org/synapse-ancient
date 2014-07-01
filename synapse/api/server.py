import json
import re

from twisted.internet import defer

from synapse.api.messages import Message
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

    @defer.inlineCallbacks
    def _on_PUT(self, request, event_id):
        print "PUT Req %s Event %s" % (request, event_id)
        try:
            put_json = json.loads(request.content.read())
            msg = Message(sender_synid=put_json["from"], body=put_json["params"]["body"],
                          type=put_json["type"])
        except ValueError:
            defer.returnValue((400, error("Content must be JSON.")))
            return
        except KeyError:
            defer.returnValue((400, error("Missing required JSON keys.")))
            return

        yield msg.save()
        print msg
        defer.returnValue((200, { "state" : "saved" }))

        
    # @defer.inlineCallbacks
    def _on_GET(self, request):
        print "GET Req %s" % request
        if "baseVer" not in request.args:
            # defer.returnValue((400, error("Missing baseVer")))
            return (400, error("Missing baseVer"))
        # defer.returnValue((200, { "data" : "Not yet implemented." } ))
        return (200, { "data" : "Not yet implemented." })
    
def error(msg):
    return { "error" : msg }
