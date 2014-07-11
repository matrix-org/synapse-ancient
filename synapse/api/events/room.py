# -*- coding: utf-8 -*-
""" This module contains events to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import (EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent,
                    InvalidHttpRequestError)
from synapse.api.auth import Auth
from synapse.api.dbobjects import Message

import json
import re


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return "sy.room.topic"

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(cls, request, room_id, auth_user_id=None):
        # TODO check they are invited/joined in the room if private. If
        # public, anyone can view the topic.

        data = yield cls.data_store.get_path_data(request.path)

        if not data:
            defer.returnValue((404, BaseEvent.error("Topic not found.")))
        defer.returnValue((200, json.loads(data[0].content)))

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, room_id, auth_user_id=None):
        try:
            # TODO check they are joined in the room

            # validate JSON
            content = BaseEvent.get_valid_json(request.content.read(),
                                               [("topic", unicode)])

            # store in db
            yield cls.data_store.store_path_data(room_id=room_id,
                path=request.path,
                content=json.dumps(content))

            # TODO poke notifier
            # TODO send to s2s layer
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        defer.returnValue((200, ""))


class RoomMemberEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return "sy.room.members.state"

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(cls, request, roomid, userid, auth_user_id=None):
        # TODO check they are joined in the room

        # Pull out the membership from the db

        result = yield cls.data_store.get_room_member(user_id=userid,
                                                      room_id=roomid)
        if not result:
            defer.returnValue((404, BaseEvent.error("Member not found.")))
        defer.returnValue((200, json.loads(result[0].content)))

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, roomid, userid, auth_user_id=None):
        try:
            # validate json
            content = BaseEvent.get_valid_json(request.content.read(),
                                               [("membership", unicode)])

            if content["membership"] not in ["join", "invite", "leave"]:
                raise InvalidHttpRequestError(400,
                    "Bad membership value. Must be one of join/invite/leave.")

            # TODO
            # invite = they != userid & they are currently joined
            # join = they == userid & they are invited or its a new room by them
            # leave = they == userid & they are currently joined

            # store membership
            yield cls.data_store.store_room_member(user_id=userid,
                                                   room_id=roomid,
                                                   content=content)

            # TODO poke notifier
            # TODO send to s2s layer
            defer.returnValue((200, ""))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        defer.returnValue((500, ""))


class MessageEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                   BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/messages/" +
                          "(?P<from>[^/]*)/(?P<msgid>[^/]*)$")

    def get_event_type(self):
        return "sy.room.message"

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(cls, request, room_id, msg_sender_id, msg_id,
               auth_user_id=None):
        # TODO check they are joined in the room

        # Pull out the message from the db
        results = yield Message.find(where=["room_id=? AND msg_id=? AND " +
                                            "user_id=?", room_id, msg_id,
                                             msg_sender_id])
        if len(results) == 0:
            defer.returnValue((404, BaseEvent.error("Message not found.")))
        defer.returnValue((200, json.loads(results[0].content)))

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, room_id, sender_id, msg_id,
               auth_user_id=None):
        try:
            # verify they are sending msgs under their own user id
            if sender_id != auth_user_id:
                raise InvalidHttpRequestError(403, "Invalid userid.")
            # check the json
            req = BaseEvent.get_valid_json(request.content.read(),
                                           [("msgtype", unicode)])
            # TODO Check if sender_id is in room room_id

            # store message in db
            yield Message(user_id=sender_id, room_id=room_id,
                          msg_id=msg_id, content=json.dumps(req)).save()

            # TODO poke notifier to send message to online users
            # TODO send to s2s layer

        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        defer.returnValue((200, ""))
