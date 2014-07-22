# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError
from synapse.api.errors import SynapseError, cs_error
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                     RoomMemberEvent)
from synapse.api.constants import Membership

import json
import re


class RoomCreateRestServlet(RestServlet):

    def register(self, http_server):
        # /rooms OR /rooms/<roomid>
        http_server.register_path("POST",
                                  re.compile("^/rooms$"),
                                  self.on_POST)
        http_server.register_path("PUT",
                                  re.compile("^/rooms/(?P<roomid>[^/]*)$"),
                                  self.on_PUT)
        # define CORS for all of /rooms in RoomCreateRestServlet for simplicity
        http_server.register_path("OPTIONS",
                                  re.compile("^/rooms(?:/.*)?$"),
                                  self.on_OPTIONS)

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id):
        try:
            auth_user_id = yield (self.auth.get_user_by_req(request))

            if not room_id:
                raise InvalidHttpRequestError(400, "PUT must specify a room ID")

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user_id, room_id)

            defer.returnValue((200, info))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))
        except InvalidHttpRequestError as he:
            defer.returnValue((he.get_status_code(), he.get_response_body()))

    @defer.inlineCallbacks
    def on_POST(self, request):
        try:
            auth_user_id = yield (self.auth.get_user_by_req(request))

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user_id, None)

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

    def on_OPTIONS(self, request):
        return (200, {})


class RoomTopicRestServlet(RestServlet):

    def register(self, http_server):
        pattern = re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")
        http_server.register_path("GET", pattern, self.on_GET)
        http_server.register_path("PUT", pattern, self.on_PUT)

    def get_event_type(self):
        return RoomTopicEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            msg_handler = self.handler_factory.message_handler()
            data = yield msg_handler.get_room_path_data(
                    user_id=user_id,
                    room_id=room_id,
                    path=request.path,
                    event_type=RoomTopicEvent.TYPE
                )

            if not data:
                defer.returnValue((404, cs_error("Topic not found.")))
            defer.returnValue((200, json.loads(data.content)))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            content = _parse_json(request)

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                content=content,
                room_id=room_id,
                user_id=user_id
                )

            msg_handler = self.handler_factory.message_handler()
            yield msg_handler.store_room_path_data(
                event=event,
                path=request.path
            )
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))


class RoomMemberRestServlet(RestServlet):

    def register(self, http_server):
        pattern = re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")
        http_server.register_path("GET", pattern, self.on_GET)
        http_server.register_path("PUT", pattern, self.on_PUT)
        http_server.register_path("DELETE", pattern, self.on_DELETE)

    def get_event_type(self):
        return RoomMemberEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, member_user_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            handler = self.handler_factory.room_member_handler()
            member = yield handler.get_room_member(room_id, member_user_id,
                                                   user_id)
            if not member:
                defer.returnValue((404, cs_error("Member not found.")))
            defer.returnValue((200, json.loads(member.content)))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))

    @defer.inlineCallbacks
    def on_DELETE(self, request, roomid, member_user_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                target_user_id=member_user_id,
                room_id=roomid,
                user_id=user_id,
                membership=Membership.LEAVE,
                content={"membership": Membership.LEAVE}
                )

            handler = self.handler_factory.room_member_handler()
            yield handler.change_membership(event, broadcast_msg=True)
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, ""))
        defer.returnValue((500, ""))

    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, member_user_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            content = _parse_json(request)
            if "membership" not in content:
                raise SynapseError(400, cs_error("No membership key"))

            if (content["membership"] not in
                    [Membership.JOIN, Membership.INVITE]):
                raise SynapseError(400,
                    cs_error("Membership value must be join/invite."))

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                target_user_id=member_user_id,
                room_id=roomid,
                user_id=user_id,
                membership=content["membership"],
                content=content
                )

            handler = self.handler_factory.room_member_handler()
            yield handler.change_membership(event, broadcast_msg=True)
            defer.returnValue((200, ""))
        except SynapseError as e:
            defer.returnValue((e.code, e.msg))
        defer.returnValue((500, ""))


class MessageRestServlet(RestServlet):

    def register(self, http_server):
        pattern = re.compile("^/rooms/(?P<roomid>[^/]*)/messages/" +
                          "(?P<from>[^/]*)/(?P<msgid>[^/]*)$")
        http_server.register_path("GET", pattern, self.on_GET)
        http_server.register_path("PUT", pattern, self.on_PUT)

    def get_event_type(self):
        return MessageEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            msg_handler = self.handler_factory.message_handler()
            msg = yield msg_handler.get_message(room_id=room_id,
                                                sender_id=msg_sender_id,
                                                msg_id=msg_id,
                                                user_id=user_id
                                                )

            if not msg:
                defer.returnValue((404, cs_error("Message not found.")))

            defer.returnValue((200, json.loads(msg.content)))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id):
        try:
            user_id = yield (self.auth.get_user_by_req(request))

            if user_id != sender_id:
                raise SynapseError(403, "Must send messages as yourself.")

            content = _parse_json(request)

            event = self.event_factory.create_event(
                etype=self.get_event_type(),
                room_id=room_id,
                user_id=user_id,
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
