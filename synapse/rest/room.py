# -*- coding: utf-8 -*-
""" This module contains REST events to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import (EventStreamMixin, PutEventMixin, GetEventMixin, RestEvent,
                    PostEventMixin, DeleteEventMixin, InvalidHttpRequestError)
from synapse.api.auth import AuthDecorator
from synapse.api.errors import SynapseError, cs_error
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                     RoomMemberEvent)
from synapse.api.constants import Membership

import json
import re


class RoomCreateRestEvent(PutEventMixin, PostEventMixin, RestEvent):

    def get_pattern(self):
        # /rooms OR /rooms/<roomid>
        return re.compile(r"^/rooms(?:/(?P<roomid>[^/]*))?$")

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, auth_user_id=None):
        try:
            if not room_id:
                raise InvalidHttpRequestError(400, "PUT must specify a room ID")

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user_id, room_id)

            defer.returnValue((200, info))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))
        except InvalidHttpRequestError as he:
            defer.returnValue((he.get_status_code(), he.get_response_body()))

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_POST(self, request, room_id, auth_user_id=None):
        try:
            if room_id:
                raise InvalidHttpRequestError(400,
                          "POST must not specify a room ID")

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user_id, room_id)

            defer.returnValue((200, info))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))
        except InvalidHttpRequestError as he:
            defer.returnValue((he.get_status_code(), he.get_response_body()))

    @defer.inlineCallbacks
    def make_room(self, room_config, auth_user_id, room_id):
        handler = self.handler_factory.room_creation_handler()
        new_room_id = yield handler.create_room(
                user_id=auth_user_id,
                room_id=room_id,
                config=room_config
        )
        defer.returnValue({
            "room_id": new_room_id
        })

    def get_room_config(self, request):
        try:
            user_supplied_config = json.loads(request.content.read())
            if "visibility" not in user_supplied_config:
                # default visibility
                user_supplied_config["visibility"] = "public"
            return user_supplied_config
        except (ValueError, TypeError):
            raise InvalidHttpRequestError(400, "Body must be JSON.")


class RoomTopicRestEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                         RestEvent):

    def get_pattern(self):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return RoomTopicEvent.TYPE

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, auth_user_id=None):
        try:
            # TODO: Change this so not to use an event.

            msg_handler = self.handler_factory.message_handler()
            data = yield msg_handler.get_room_path_data(
                    room_id=room_id,
                    event_type=self.get_event_type(),
                    auth_user_id=auth_user_id,
                    path=request.path
                )

            if not data:
                defer.returnValue((404, cs_error("Topic not found.")))
            defer.returnValue((200, json.loads(data[0].content)))
        except SynapseError as e:
            defer.returnValue((e.code, ""))

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, auth_user_id=None):
        try:
            content = _parse_json(request)

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                content=content,
                room_id=room_id,
                sender=auth_user_id,
                auth_user_id=auth_user_id,
                )

            msg_handler = self.handler_factory.message_handler()
            yield msg_handler.store_room_path_data(
                event=event,
                path=request.path
            )
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))


class RoomMemberRestEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                          DeleteEventMixin, RestEvent):

    def get_pattern(self):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return RoomMemberEvent.TYPE

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_GET(self, request, roomid, userid, auth_user_id=None):
        try:
            handler = self.handler_factory.room_member_handler()
            member = yield handler.get_room_member(roomid, userid)

            if not member:
                defer.returnValue((404, cs_error("Member not found.")))
            defer.returnValue((200, json.loads(member.content)))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_DELETE(self, request, roomid, userid, auth_user_id=None):
        try:
            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                target_user=userid,
                room_id=roomid,
                sender=auth_user_id,
                auth_user_id=auth_user_id,
                content={"membership": Membership.LEAVE}
                )

            handler = self.handler_factory.room_member_handler()
            yield handler.change_membership(event, broadcast_msg=True)
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, ""))
        defer.returnValue((500, ""))

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, userid, auth_user_id=None):
        try:
            content = _parse_json(request)
            if "membership" not in content:
                raise SynapseError(400, cs_error("No membership key"))

            if (content["membership"] not in
                    [Membership.JOIN, Membership.INVITE]):
                raise SynapseError(400,
                    cs_error("Membership value must be join/invite."))

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                target_user=userid,
                room_id=roomid,
                sender=auth_user_id,
                auth_user_id=auth_user_id,
                content=content
                )

            handler = self.handler_factory.room_member_handler()
            yield handler.change_membership(event, broadcast_msg=True)
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))
        defer.returnValue((500, ""))


class MessageRestEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                       RestEvent):

    def get_pattern(self):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/messages/" +
                          "(?P<from>[^/]*)/(?P<msgid>[^/]*)$")

    def get_event_type(self):
        return MessageEvent.TYPE

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id,
               auth_user_id=None):
        try:
            msg_handler = self.handler_factory.message_handler()
            msg = yield msg_handler.get_message(
                auth_user_id, room_id, msg_sender_id, msg_id
            )

            if not msg:
                defer.returnValue((404, cs_error("Message not found.")))

            defer.returnValue((200, json.loads(msg.content)))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

    @AuthDecorator.defer_verify_token
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id,
               auth_user_id=None):
        try:
            content = _parse_json(request)

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                room_id=room_id,
                sender=sender_id,
                auth_user_id=auth_user_id,
                msg_id=msg_id,
                content=content
                )

            msg_handler = self.handler_factory.message_handler()
            yield msg_handler.send_message(event)
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

        defer.returnValue((200, ""))


def _parse_json(request):
    try:
        return json.loads(request.content.read())
    except ValueError:
        raise SynapseError(400, "Content not JSON.")
