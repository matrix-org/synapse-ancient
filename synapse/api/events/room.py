# -*- coding: utf-8 -*-
""" This module contains events to do with rooms: /rooms/<paths> """
from twisted.internet import defer

from base import (EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent,
                    PostEventMixin, DeleteEventMixin, InvalidHttpRequestError)
from synapse.api.auth import Auth
from synapse.api.event_store import StoreException

import json
import re
import time


class RoomCreateEvent(PutEventMixin, PostEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        # /rooms OR /rooms/<roomid>
        return re.compile(r"^/rooms(?:/(?P<roomid>[^/]*))?$")

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, room_id, auth_user_id=None):
        try:
            if not room_id:
                raise InvalidHttpRequestError(400, "PUT must specify a room ID")

            room_config = cls.get_room_config(request)
            new_room_info = yield cls._create_room(room_id, room_config,
                                                   auth_user_id)

            defer.returnValue((200, new_room_info))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_POST(cls, request, room_id, auth_user_id=None):
        try:
            if room_id:
                raise InvalidHttpRequestError(400,
                          "POST must not specify a room ID")
            room_config = cls.get_room_config(request)
            new_room_info = yield cls._create_room(room_id, room_config,
                                                   auth_user_id)

            defer.returnValue((200, new_room_info))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

    @classmethod
    @defer.inlineCallbacks
    def _create_room(cls, room_id, room_config, user_id):
        try:
            new_room_id = yield cls.data_store.store_room(
                room_id=room_id,
                room_creator_user_id=user_id,
                is_public=room_config["visibility"] == "public"
            )
            if not new_room_id:
                raise InvalidHttpRequestError(409, "Room ID in use.")

            defer.returnValue({
                "room_id": new_room_id
            })
        except StoreException:
            raise InvalidHttpRequestError(500, "Unable to create room.")

    @classmethod
    def get_room_config(cls, request):
        try:
            user_supplied_config = json.loads(request.content.read())
            if "visibility" not in user_supplied_config:
                # default visibility
                user_supplied_config["visibility"] = "public"
            return user_supplied_config
        except (ValueError, TypeError):
            raise InvalidHttpRequestError(400, "Body must be JSON.")


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
        try:
            # does this room exist
            room = yield cls.data_store.get_room(room_id)
            if not room:
                defer.returnValue((403, ""))

            # is it public or private? If it's public, anyone can see the topic.
            # If it is private, make sure they are joined/invited first.
            if not room[0].is_public:
                # it's private, check they are invited/joined in the room
                member = yield cls.data_store.get_room_member(
                        room_id=room_id,
                        user_id=auth_user_id)
                if not member or member[0].membership not in ["join", "invite"]:
                    raise InvalidHttpRequestError(403, "")

            data = yield cls.data_store.get_path_data(request.path)

            if not data:
                defer.returnValue((404, BaseEvent.error("Topic not found.")))
            defer.returnValue((200, json.loads(data[0].content)))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, room_id, auth_user_id=None):
        try:
            # check they are joined in the room
            yield get_joined_or_throw(cls.data_store,
                                      room_id=room_id,
                                      user_id=auth_user_id)

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
                      DeleteEventMixin, BaseEvent):

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
    def on_DELETE(cls, request, roomid, userid, auth_user_id=None):
        try:
            # does this room even exist
            room = cls.data_store.get_room(roomid)
            if not room:
                raise InvalidHttpRequestError(403, "")

            caller = yield cls.data_store.get_room_member(user_id=auth_user_id,
                                                    room_id=roomid)
            caller_in_room = caller and caller[0].membership == "join"

            if not caller_in_room or userid != auth_user_id:
                # trying to leave a room you aren't joined or trying to force
                # another user to leave
                raise InvalidHttpRequestError(403, "")

            # store membership
            yield cls.data_store.store_room_member(user_id=userid,
                                                   room_id=roomid,
                                                   membership="leave")

            cls._inject_membership_msg(
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

    @classmethod
    @Auth.defer_registered_user
    @defer.inlineCallbacks
    def on_PUT(cls, request, roomid, userid, auth_user_id=None):
        try:
            # validate json
            content = BaseEvent.get_valid_json(request.content.read(),
                                               [("membership", unicode)])

            if content["membership"] not in ["join", "invite"]:
                raise InvalidHttpRequestError(400,
                    "Bad membership value. Must be one of join/invite.")

            # does this room even exist
            room = cls.data_store.get_room(roomid)
            if not room:
                raise InvalidHttpRequestError(403, "")

            caller = yield cls.data_store.get_room_member(user_id=auth_user_id,
                                                    room_id=roomid)
            caller_in_room = caller and caller[0].membership == "join"

            target = yield cls.data_store.get_room_member(user_id=userid,
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
                yield cls.data_store.store_room_member(
                    user_id=userid,
                    room_id=roomid,
                    membership=content["membership"],
                    content=content)

                cls._inject_membership_msg(
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

    @classmethod
    @defer.inlineCallbacks
    def _inject_membership_msg(cls, room_id=None, source=None, target=None,
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
        yield cls.data_store.store_message(
            user_id="home_server",
            room_id=room_id,
            msg_id=msg_id,
            content=json.dumps(membership_json))


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
        try:
            # check they are joined in the room
            yield get_joined_or_throw(cls.data_store,
                                      room_id=room_id,
                                      user_id=auth_user_id)

            # Pull out the message from the db
            results = yield cls.data_store.get_message(room_id=room_id,
                                                       msg_id=msg_id,
                                                       user_id=msg_sender_id)
            if not results:
                defer.returnValue((404, BaseEvent.error("Message not found.")))
            defer.returnValue((200, json.loads(results[0].content)))
        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

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

            # Check if sender_id is in room room_id
            yield get_joined_or_throw(cls.data_store,
                                      room_id=room_id,
                                      user_id=auth_user_id)

            # store message in db
            yield cls.data_store.store_message(user_id=sender_id,
                                               room_id=room_id,
                                               msg_id=msg_id,
                                               content=json.dumps(req))

            # TODO poke notifier to send message to online users
            # TODO send to s2s layer

        except InvalidHttpRequestError as e:
            defer.returnValue((e.get_status_code(), e.get_response_body()))

        defer.returnValue((200, ""))


# TODO this should probably go somewhere else?
@defer.inlineCallbacks
def get_joined_or_throw(store=None, user_id=None, room_id=None):
    """Utility method to return the specified room member.

    Args:
        store : The event data store
        user_id : The member's ID
        room_id : The room where the member is joined.
    Returns:
        The room member.
    Raises:
        InvalidHttpRequestError if this member does not exist/isn't joined.
    """
    member = yield store.get_room_member(
                        room_id=room_id,
                        user_id=user_id)
    if not member or member[0].membership != "join":
        raise InvalidHttpRequestError(403, "")
    defer.returnValue(member)