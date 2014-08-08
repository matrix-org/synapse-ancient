# -*- coding: utf-8 -*-
""" This module contains REST servlets to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import RestServlet, InvalidHttpRequestError, client_path_pattern
from synapse.api.errors import SynapseError, cs_error
from synapse.api.events.room import (RoomTopicEvent, MessageEvent,
                                     RoomMemberEvent, FeedbackEvent)
from synapse.api.constants import Feedback, Membership
from synapse.api.streams import PaginationConfig

import json
import urllib


class RoomCreateRestServlet(RestServlet):
    # No PATTERN; we have custom dispatch rules here

    def register(self, http_server):
        # /rooms OR /rooms/<roomid>
        http_server.register_path("POST",
                                  client_path_pattern("/rooms$"),
                                  self.on_POST)
        http_server.register_path("PUT",
                                  client_path_pattern(
                                      "/rooms/(?P<room_id>[^/]*)$"),
                                  self.on_PUT)
        # define CORS for all of /rooms in RoomCreateRestServlet for simplicity
        http_server.register_path("OPTIONS",
                                  client_path_pattern("/rooms(?:/.*)?$"),
                                  self.on_OPTIONS)

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id):
        try:
            room_id = urllib.unquote(room_id)
            auth_user = yield self.auth.get_user_by_req(request)

            if not room_id:
                raise InvalidHttpRequestError(
                    400, "PUT must specify a room ID")

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user, room_id)
            info.update(room_config)
            defer.returnValue((200, info))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))
        except InvalidHttpRequestError as he:
            defer.returnValue((he.get_status_code(), he.get_response_body()))

    @defer.inlineCallbacks
    def on_POST(self, request):
        try:
            auth_user = yield self.auth.get_user_by_req(request)

            room_config = self.get_room_config(request)
            info = yield self.make_room(room_config, auth_user, None)
            info.update(room_config)
            defer.returnValue((200, info))
        except SynapseError as e:
            defer.returnValue((e.code, cs_error(e.msg)))
        except InvalidHttpRequestError as he:
            defer.returnValue((he.get_status_code(), he.get_response_body()))

    @defer.inlineCallbacks
    def make_room(self, room_config, auth_user, room_id):
        handler = self.handlers.room_creation_handler
        new_room_id = yield handler.create_room(
            user_id=auth_user.to_string(),
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
    PATTERN = client_path_pattern("/rooms/(?P<room_id>[^/]*)/topic$")

    def get_event_type(self):
        return RoomTopicEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id):
        user = yield self.auth.get_user_by_req(request)

        msg_handler = self.handlers.message_handler
        data = yield msg_handler.get_room_data(
            user_id=user.to_string(),
            room_id=urllib.unquote(room_id),
            event_type=RoomTopicEvent.TYPE,
            state_key="",
        )

        if not data:
            defer.returnValue((404, cs_error("Topic not found.")))
        defer.returnValue((200, json.loads(data.content)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id):
        user = yield self.auth.get_user_by_req(request)

        content = _parse_json(request)

        event = self.event_factory.create_event(
            etype=self.get_event_type(),
            content=content,
            room_id=urllib.unquote(room_id),
            user_id=user.to_string(),
            )

        msg_handler = self.handlers.message_handler
        yield msg_handler.store_room_data(
            event=event
        )
        defer.returnValue((200, ""))


class RoomMemberRestServlet(RestServlet):
    PATTERN = client_path_pattern("/rooms/(?P<room_id>[^/]*)/members/"
                                  + "(?P<target_user_id>[^/]*)/state$")

    def get_event_type(self):
        return RoomMemberEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, target_user_id):
        room_id = urllib.unquote(room_id)
        user = yield self.auth.get_user_by_req(request)

        handler = self.handlers.room_member_handler
        member = yield handler.get_room_member(room_id, target_user_id,
                                               user.to_string())
        if not member:
            defer.returnValue((404, cs_error("Member not found.")))
        defer.returnValue((200, json.loads(member.content)))

    @defer.inlineCallbacks
    def on_DELETE(self, request, roomid, target_user_id):
        user = yield self.auth.get_user_by_req(request)

        event = self.event_factory.create_event(
            etype=self.get_event_type(),
            target_user_id=target_user_id,
            room_id=urllib.unquote(roomid),
            user_id=user.to_string(),
            membership=Membership.LEAVE,
            content={"membership": Membership.LEAVE}
            )

        handler = self.handlers.room_member_handler
        yield handler.change_membership(event, broadcast_msg=True)
        defer.returnValue((200, ""))

    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, target_user_id):
        user = yield self.auth.get_user_by_req(request)

        content = _parse_json(request)
        if "membership" not in content:
            raise SynapseError(400, cs_error("No membership key"))

        valid_membership_values = [Membership.JOIN, Membership.INVITE]
        if (content["membership"] not in valid_membership_values):
            raise SynapseError(
                400, cs_error("Membership value must be %s." % (
                    valid_membership_values,
                ))
            )

        event = self.event_factory.create_event(
            etype=self.get_event_type(),
            target_user_id=target_user_id,
            room_id=urllib.unquote(roomid),
            user_id=user.to_string(),
            membership=content["membership"],
            content=content
            )

        handler = self.handlers.room_member_handler
        result = yield handler.change_membership(event, broadcast_msg=True)
        defer.returnValue((200, result))


class MessageRestServlet(RestServlet):
    PATTERN = client_path_pattern("/rooms/(?P<room_id>[^/]*)/messages/"
                                  + "(?P<sender_id>[^/]*)/(?P<msg_id>[^/]*)$")

    def get_event_type(self):
        return MessageEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, sender_id, msg_id):
        user = yield self.auth.get_user_by_req(request)

        msg_handler = self.handlers.message_handler
        msg = yield msg_handler.get_message(room_id=urllib.unquote(room_id),
                                            sender_id=sender_id,
                                            msg_id=msg_id,
                                            user_id=user.to_string(),
                                            )

        if not msg:
            defer.returnValue((404, cs_error("Message not found.")))

        defer.returnValue((200, json.loads(msg.content)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id):
        user = yield self.auth.get_user_by_req(request)

        if user.to_string() != sender_id:
            raise SynapseError(403, "Must send messages as yourself.")

        content = _parse_json(request)

        event = self.event_factory.create_event(
            etype=self.get_event_type(),
            room_id=urllib.unquote(room_id),
            user_id=user.to_string(),
            msg_id=msg_id,
            content=content
            )

        msg_handler = self.handlers.message_handler
        yield msg_handler.send_message(event)

        defer.returnValue((200, ""))


class FeedbackRestServlet(RestServlet):
    PATTERN = client_path_pattern(
        "/rooms/(?P<room_id>[^/]*)/messages/" +
        "(?P<msg_sender_id>[^/]*)/(?P<msg_id>[^/]*)/feedback/" +
        "(?P<sender_id>[^/]*)/(?P<feedback_type>[^/]*)$"
    )

    def get_event_type(self):
        return FeedbackEvent.TYPE

    @defer.inlineCallbacks
    def on_GET(self, request, room_id, msg_sender_id, msg_id, fb_sender_id,
               feedback_type):
        user = yield (self.auth.get_user_by_req(request))

        if feedback_type not in Feedback.LIST:
            raise SynapseError(400, "Bad feedback type.")

        msg_handler = self.handlers.message_handler
        feedback = yield msg_handler.get_feedback(
            room_id=urllib.unquote(room_id),
            msg_sender_id=msg_sender_id,
            msg_id=msg_id,
            user_id=user.to_string(),
            fb_sender_id=fb_sender_id,
            fb_type=feedback_type
        )

        if not feedback:
            defer.returnValue((404, cs_error("Feedback not found.")))

        defer.returnValue((200, json.loads(feedback.content)))

    @defer.inlineCallbacks
    def on_PUT(self, request, room_id, sender_id, msg_id, fb_sender_id,
               feedback_type):
        user = yield (self.auth.get_user_by_req(request))

        if user.to_string() != fb_sender_id:
            raise SynapseError(403, "Must send feedback as yourself.")

        if feedback_type not in Feedback.LIST:
            raise SynapseError(400, "Bad feedback type.")

        content = _parse_json(request)

        event = self.event_factory.create_event(
            etype=self.get_event_type(),
            room_id=urllib.unquote(room_id),
            msg_sender_id=sender_id,
            msg_id=msg_id,
            user_id=user.to_string(),  # user sending the feedback
            feedback_type=feedback_type,
            content=content
            )

        msg_handler = self.handlers.message_handler
        yield msg_handler.send_feedback(event)

        defer.returnValue((200, ""))


class RoomMemberListRestServlet(RestServlet):
    PATTERN = client_path_pattern("/rooms/(?P<room_id>[^/]*)/members/list$")

    @defer.inlineCallbacks
    def on_GET(self, request, room_id):
        # TODO support Pagination stream API (limit/tokens)
        user = yield self.auth.get_user_by_req(request)
        handler = self.handlers.room_member_handler
        members = yield handler.get_room_members_as_pagination_chunk(
            room_id=urllib.unquote(room_id),
            user_id=user.to_string())

        defer.returnValue((200, members))


class RoomMessageListRestServlet(RestServlet):
    PATTERN = client_path_pattern("/rooms/(?P<room_id>[^/]*)/messages/list$")

    @defer.inlineCallbacks
    def on_GET(self, request, room_id):
        user = yield self.auth.get_user_by_req(request)
        pagination_config = PaginationConfig.from_request(request)
        with_feedback = "feedback" in request.args
        handler = self.handlers.message_handler
        msgs = yield handler.get_messages(
            room_id=urllib.unquote(room_id),
            user_id=user.to_string(),
            pagin_config=pagination_config,
            feedback=with_feedback)

        defer.returnValue((200, msgs))


def _parse_json(request):
    try:
        content = json.loads(request.content.read())
        if type(content) != dict:
            raise SynapseError(400, "Content must be a JSON object.")
        return content
    except ValueError:
        raise SynapseError(400, "Content not JSON.")


def register_servlets(hs, http_server):
    RoomTopicRestServlet(hs).register(http_server)
    RoomMemberRestServlet(hs).register(http_server)
    MessageRestServlet(hs).register(http_server)
    FeedbackRestServlet(hs).register(http_server)
    RoomCreateRestServlet(hs).register(http_server)
    RoomMemberListRestServlet(hs).register(http_server)
    RoomMessageListRestServlet(hs).register(http_server)
