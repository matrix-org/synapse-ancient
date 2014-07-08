from twisted.internet import defer

from events import (EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent,
                    InvalidHttpRequestError)
from auth import AccessTokenAuth
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
        return (200, {"rooms": "None"})

    @AccessTokenAuth.authenticate
    def on_PUT(self, request, *url_args):
        # TODO:
        # Auth user & check they are joined in the room
        # store topic
        # poke notifier
        # send to s2s layer
        try:
            BaseEvent.get_valid_json(request.content.read(),
                                     [("topic", unicode)])
        except InvalidHttpRequestError as e:
            return (e.get_status_code(), e.get_response_body())
        return (200, "")


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

    @AccessTokenAuth.deferAuthenticate
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
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

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

    @AccessTokenAuth.deferAuthenticate
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
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        msg = Message(sender_id=sender_id, room_id=room_id,
                      msg_id=msg_id, content=json.dumps(req))
        yield msg.save()
        defer.returnValue((200, ""))