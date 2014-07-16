# -*- coding: utf-8 -*-
""" This module contains events to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import (EventStreamMixin, PutEventMixin, GetEventMixin, RestEvent,
                    PostEventMixin, DeleteEventMixin, InvalidHttpRequestError)
from synapse.api.auth import Auth
from synapse.api.errors import SynapseError, cs_error
from synapse.api.events.room import GlobalMsgId

import json
import re
import time


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
        # TODO check they are joined in the room

        # Pull out the membership from the db

        result = yield self.data_store.get_room_member(user_id=userid,
                                                      room_id=roomid)
        if not result:
            defer.returnValue((404, cs_error("Member not found.")))
        defer.returnValue((200, json.loads(result[0].content)))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_DELETE(self, request, roomid, userid, auth_user_id=None):
        try:
            # does this room even exist
            room = self.data_store.get_room(roomid)
            if not room:
                raise InvalidHttpRequestError(403, "")

            caller = yield self.data_store.get_room_member(user_id=auth_user_id,
                                                    room_id=roomid)
            caller_in_room = caller and caller[0].membership == "join"

            if not caller_in_room or userid != auth_user_id:
                # trying to leave a room you aren't joined or trying to force
                # another user to leave
                raise InvalidHttpRequestError(403, "")

            # store membership
            yield self.data_store.store_room_member(user_id=userid,
                                                   room_id=roomid,
                                                   membership="leave")

            self._inject_membership_msg(
                    source=auth_user_id,
                    target=userid,
                    room_id=roomid,
                    membership="leave")

            # TODO poke notifier
            # TODO send to s2s layer
            defer.returnValue((200, ""))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        defer.returnValue((500, ""))

    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(self, request, roomid, userid, auth_user_id=None):
        try:
            # validate json
            content = RestEvent.get_valid_json(request.content.read(),
                                               [("membership", unicode)])

            if content["membership"] not in ["join", "invite"]:
                raise InvalidHttpRequestError(400,
                    "Bad membership value. Must be one of join/invite.")

            # does this room even exist
            room = self.data_store.get_room(roomid)
            if not room:
                raise InvalidHttpRequestError(403, "")

            caller = yield self.data_store.get_room_member(user_id=auth_user_id,
                                                    room_id=roomid)
            caller_in_room = caller and caller[0].membership == "join"

            target = yield self.data_store.get_room_member(user_id=userid,
                                                    room_id=roomid)
            target_in_room = target and target[0].membership == "join"

            valid_op = False
            if content["membership"] == "invite":
                # Invites are valid iff caller is in the room and target isn't.
                if caller_in_room and not target_in_room:
                    valid_op = True
            elif content["membership"] == "join":
                # Joins are valid iff caller == target and they were:
                # invited: They are accepting the invitation
                # joined: It's a NOOP
                if (auth_user_id == userid and caller and
                    caller[0].membership in ["invite", "join"]):
                    valid_op = True
            else:
                raise Exception("Unknown membership %s" % content["membership"])

            if valid_op:
                # store membership
                yield self.data_store.store_room_member(
                    user_id=userid,
                    room_id=roomid,
                    membership=content["membership"],
                    content=content)

                self._inject_membership_msg(
                    source=auth_user_id,
                    target=userid,
                    room_id=roomid,
                    membership=content["membership"])

                # TODO poke notifier
                # TODO send to s2s layer
                defer.returnValue((200, ""))
            else:
                raise InvalidHttpRequestError(403, "")
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))
        defer.returnValue((500, ""))

    @defer.inlineCallbacks
    def _inject_membership_msg(self, room_id=None, source=None, target=None,
                               membership=None):
        # TODO move this somewhere else.
        # TODO this should be a different type of message, not sy.text
        if membership == "invite":
            body = "%s invited %s to the room." % (source, target)
        elif membership == "join":
            body = "%s joined the room." % (target)
        elif membership == "leave":
            body = "%s left the room." % (target)
        else:
            raise Exception("Unknown membership value %s" % membership)

        membership_json = {
            "msgtype": "sy.text",
            "body": body
        }
        msg_id = "m%s" % int(time.time())
        yield self.data_store.store_message(
            user_id="home_server",
            room_id=room_id,
            msg_id=msg_id,
            content=json.dumps(membership_json))


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
