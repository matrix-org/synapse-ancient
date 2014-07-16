# -*- coding: utf-8 -*-
""" This module contains events to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import (EventStreamMixin, PutEventMixin, GetEventMixin, RestEvent,
                    PostEventMixin, DeleteEventMixin, InvalidHttpRequestError)
from synapse.api.auth import Auth
from synapse.api.errors import SynapseError, cs_error
from synapse.api.events.room import GlobalMsgId, Membership

import json
import re


class RoomCreateRestEvent(PutEventMixin, PostEventMixin, RestEvent):

    def get_pattern(self):
        # /rooms OR /rooms/<roomid>
        return re.compile(r"^/rooms(?:/(?P<roomid>[^/]*))?$")

    @Auth.defer_registered_user
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

    @Auth.defer_registered_user
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
        event = self.event_factory.room_creation_event()
        new_room_id = yield event.create_room(
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
        return "sy.room.topic"

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, auth_user_id=None):
        try:
            msg_event = self.event_factory.message_event()
            data = yield msg_event.get_room_path_data(
                    room_id=room_id,
                    user_id=auth_user_id,
                    path=request.path,
                    # anyone invited/joined can read the topic
                    private_room_rules=["invite", "join"]
                )

            if not data:
                defer.returnValue((404, cs_error("Topic not found.")))
            defer.returnValue((200, json.loads(data[0].content)))
        except SynapseError as e:
            defer.returnValue((e.code, ""))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, auth_user_id=None):
        try:
            content = _parse_json(request)

            msg_event = self.event_factory.message_event()
            yield msg_event.store_room_path_data(
                room_id=room_id,
                user_id=auth_user_id,
                content=content,
                path=request.path
            )
            # TODO poke notifier
            # TODO send to s2s layer
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))


class RoomMemberRestEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                          DeleteEventMixin, RestEvent):

    def get_pattern(self):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return "sy.room.members.state"

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(self, request, roomid, userid, auth_user_id=None):

        event = self.event_factory.room_member_event()
        member = yield event.get_room_member(
            user_id=userid,
            auth_user_id=auth_user_id,
            room_id=roomid
        )

        if not member:
            defer.returnValue((404, cs_error("Member not found.")))
        defer.returnValue((200, json.loads(member.content)))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_DELETE(self, request, roomid, userid, auth_user_id=None):
        try:
            event = self.event_factory.room_member_event()
            yield event.change_membership(
                auth_user_id=auth_user_id,
                user_id=userid,
                room_id=roomid,
                membership=Membership.leave,
                broadcast_msg=True
            )
            # TODO poke notifier
            # TODO send to s2s layer
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))
        defer.returnValue((500, ""))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, userid, auth_user_id=None):
        try:
            content = _parse_json(request)
            if "membership" not in content:
                raise SynapseError(400, cs_error("No membership key"))

            if (content["membership"] not in
                    [Membership.join, Membership.invite]):
                raise SynapseError(400,
                    cs_error("Membership value must be join/invite."))

            event = self.event_factory.room_member_event()
            yield event.change_membership(
                auth_user_id=auth_user_id,
                user_id=userid,
                room_id=roomid,
                membership=content["membership"],
                content=content,
                broadcast_msg=True
            )
            # TODO poke notifier
            # TODO send to s2s layer
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
        return "sy.room.message"

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id,
               auth_user_id=None):
        try:
            msg_event = self.event_factory.message_event()
            msg = yield msg_event.get_message(
                global_msg=GlobalMsgId(room_id=room_id,
                                        user_id=msg_sender_id,
                                        msg_id=msg_id),
                user_id=auth_user_id
            )

            if not msg:
                defer.returnValue((404, cs_error("Message not found.")))

            defer.returnValue((200, json.loads(msg.content)))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id,
               auth_user_id=None):
        try:
            content = _parse_json(request)

            msg_event = self.event_factory.message_event()
            yield msg_event.store_message(
                global_msg=GlobalMsgId(room_id=room_id,
                                        user_id=sender_id,
                                        msg_id=msg_id),
                content=content,
                user_id=auth_user_id
            )
            # TODO poke notifier to send message to online users
            # TODO send to s2s layer
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

        defer.returnValue((200, ""))


def _parse_json(request):
    try:
        return json.loads(request.content.read())
    except ValueError:
        raise SynapseError(400, "Content not JSON.")
