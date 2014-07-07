from twisted.internet import defer

from events import EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent
from synapse.api.messages import Message

import json
import re


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return "sy.room.topic"

    def on_GET(self, request, *url_args):
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"rooms": "None"})

    def on_PUT(self, request, *url_args):
        try:
            req = BaseEvent.get_valid_json(request.content.read(), ["topic"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"topic": req["topic"]})


class RoomMemberEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return "sy.room.members.state"

    def on_GET(self, request, *url_args):
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"membership": "None"})

    def on_PUT(self, request, *url_args):
        try:
            req = BaseEvent.get_valid_json(request.content.read(),
                                           ["membership"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"membership": req["membership"]})


class MessageEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/messages/" +
                          "(?P<from>[^/]*)/(?P<msgid>[^/]*)$")

    def get_event_type(self):
        return "sy.room.message"

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id):
        results = yield Message.find(where=["room_id=? AND msg_id=? AND " +
                          "sender_id=?", room_id, msg_id, msg_sender_id])
        if len(results) == 0:
            defer.returnValue((404, BaseEvent.error("Message not found.")))
        defer.returnValue((200, json.loads(results[0].msg_json)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id):
        try:
            req = BaseEvent.get_valid_json(request.content.read(),
                                           ["msgtype", "body"])
        except ValueError:
            defer.returnValue((400, BaseEvent.error("Content must be JSON.")))
        except KeyError:
            defer.returnValue((400, BaseEvent.error("Missing required keys.")))

        msg = Message(sender_id=sender_id, room_id=room_id,
                      msg_id=msg_id, msg_json=json.dumps(req))
        yield msg.save()
        defer.returnValue((200, ""))