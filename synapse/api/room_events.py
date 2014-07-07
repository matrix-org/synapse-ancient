from twisted.internet import defer

from events import EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent
from synapse.api.messages import Message, RoomMembership

import json
import re

# TODO: Can on_PUTs which just check keys > dump in db be factored out somehow?


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return "sy.room.topic"

    def on_GET(self, request, *url_args):
        # TODO:
        # Auth user & check they are invited/joined in the room if private. If
        # public, anyone can view the topic.
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"rooms": "None"})

    def on_PUT(self, request, *url_args):
        # TODO:
        # Auth user & check they are joined in the room
        # store topic
        # poke notifier
        # send to s2s layer
        try:
            req = BaseEvent.get_valid_json(request.content.read(),
                                           [("topic", unicode)])
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

    @defer.inlineCallbacks
    def on_GET(self, request, roomid, userid):
        # TODO:
        # Auth user & check they are joined in the room
        result = yield RoomMembership.find(where=["sender_id=? AND room_id=?",
                                userid, roomid], limit=1, orderby="id DESC")
        if not result:
            defer.returnValue((404, BaseEvent.error("Member not found.")))
        defer.returnValue((200, json.loads(result.content)))

    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, userid):
        # TODO
        # Auth the user
        # invites = they != userid & they are currently joined
        # joins = they == userid & they are invited or it's a new room by them
        # leaves = they == userid & they are currently joined
        # store membership
        # poke notifier
        # send to s2s layer
        try:
            content = BaseEvent.get_valid_json(request.content.read(),
                                           [("membership", unicode)])
        except ValueError:
            defer.returnValue((400, BaseEvent.error("Content must be JSON.")))
        except KeyError:
            defer.returnValue((400, BaseEvent.error("Missing required keys.")))

        member = RoomMembership(sender_id=userid, room_id=roomid,
                                content=json.dumps(content))
        yield member.save()
        defer.returnValue((200, ""))


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
        # TODO:
        # Auth user & check they are joined in the room
        results = yield Message.find(where=["room_id=? AND msg_id=? AND " +
                          "sender_id=?", room_id, msg_id, msg_sender_id])
        if len(results) == 0:
            defer.returnValue((404, BaseEvent.error("Message not found.")))
        defer.returnValue((200, json.loads(results[0].content)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id):
        # TODO:
        # Auth the user somehow (access token) & verify they == sender_id
        # Check if sender_id is in room room_id
        # store message
        # poke notifier to send message to online users
        # send to s2s layer

        try:
            req = BaseEvent.get_valid_json(request.content.read(),
                                           [("msgtype", unicode),
                                            ("body", unicode)])
        except ValueError:
            defer.returnValue((400, BaseEvent.error("Content must be JSON.")))
        except KeyError:
            defer.returnValue((400, BaseEvent.error("Missing required keys.")))

        msg = Message(sender_id=sender_id, room_id=room_id,
                      msg_id=msg_id, content=json.dumps(req))
        yield msg.save()
        defer.returnValue((200, ""))