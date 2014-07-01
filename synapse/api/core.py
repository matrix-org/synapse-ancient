from twisted.internet import reactor, defer

from synapse.api.messages import Message
from synapse.api.messages import Presence

class SynapseApi(object):

    def __init__(self, database, notifier):
        self.database = database
        self.notifier = notifier

    @defer.inlineCallbacks
    def process_event_put(self, request, event_id, json):
        """ Called when there is a PUT to /events/$event_id.

        Args:
            request : The twisted Request
            event_id : The validated event_id from the path of the request.
            json : The syntactically-validated JSON from the body of the request
        Returns:
            A Deferred which on success contains a tuple of (code, dict) to respond with.
            The dict will be converted into JSON for you before responding.
        """
        print "SynapseApi: Event ID %s : %s" % (event_id, json)

        # validate the JSON keys
        try:
            msg_id = json["msgId"]
            msg_from = json["from"]
            room_id = json["roomId"]
            type = json["type"]
            body = json["params"]["body"]
            msg = Message(sender_synid=msg_from, body=body, type=type)
            yield msg.save()
            defer.returnValue((200, { "state" : "Saved" })) 
        except KeyError as ke:
            defer.returnValue((400, { "error" : "Missing JSON keys." } ))

        defer.returnValue((200, { "state" : "Not yet implemented" }) )

    def process_event_get(self, request, ver):
        """ Called when there is a GET to /events.

        Args:
            request : The twisted Request
            ver : The base version requested, extracted from the GET parameters.
        Returns:
            A Deferred which on success contains a tuple of (code, dict) to respond with.
            The dict will be converted into JSON for you before responding.
        """
        print "SynapseApi: Version %s" % ver
        return defer.succeed((200, { "request" : "Not yet implemented"}))

    def process_incoming_data(self, data):
        if data.type == Message.TEXT:
            self.database.store_message(data)
            self.notifier.process_incoming_message(data)
        elif data.type == Presence.TYPE:
            msgs = self.database.get_messages(data.sender_synid)
            if msgs:
                self.notifier.notify_user_for_messages(msgs)

        return defer.succeed(True)

