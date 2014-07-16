# -*- coding: utf-8 -*-
"""Contains functions for performing events on rooms."""
from twisted.internet import defer

from synapse.api.errors import RoomError
from synapse.util.stringutils import JSONTemplate

from collections import namedtuple
import json


class GlobalMsgId(namedtuple("GlobalMsgId",
                                ["room_id", "user_id", "msg_id"])):
    """ Groups room/user/msg IDs to make a globally unique ID."""

    def global_id(self):
        return "%s-%s-%s" % (self.room_id, self.user_id, self.msg_id)


class MessageEvent(object):

    def __init__(self, event_store):
        self.store = event_store

    @defer.inlineCallbacks
    def get_message(self, global_msg=None, user_id=None):
        """ Retrieve a message.

        Args:
            global_msg (GlobalMsgId) : All the IDs used to locate the message.
            user_id (str): Checks this user has permissions to read this
            message. If None, no check is performed.
        Returns:
            The message, or None if no message exists.
        Raises:
            RoomError if something went wrong.
        """
        if user_id:
            # check they are joined in the room
            yield _get_joined_or_throw(self.store,
                                      room_id=global_msg.room_id,
                                      user_id=user_id)

        # Pull out the message from the db
        results = yield self.store.get_message(room_id=global_msg.room_id,
                                               msg_id=global_msg.msg_id,
                                               user_id=global_msg.user_id)

        if results:
            defer.returnValue(results[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def store_message(self, global_msg=None, content=None, user_id=None):
        """ Store a message.

        Args:
            global_msg (GlobalMsgId) : All the IDs used to identify the
            message.
            content : The JSON content to store.
            user_id (str): Checks this user has permissions to send this
            message. If None, no check is performed.
        Raises:
            SynapseError if something went wrong.
        """
        if user_id:
            # verify they are sending msgs under their own user id
            if global_msg.user_id != user_id:
                raise RoomError(403, "Must send messages as yourself.")

            # Check if sender_id is in room room_id
            yield _get_joined_or_throw(self.store,
                                      room_id=global_msg.room_id,
                                      user_id=global_msg.user_id)

        template = JSONTemplate({"msgtype": u"str"})
        template.check_json(content)

        # store message in db
        yield self.store.store_message(user_id=global_msg.user_id,
                                       room_id=global_msg.room_id,
                                       msg_id=global_msg.msg_id,
                                       content=json.dumps(content))

    @defer.inlineCallbacks
    def store_room_path_data(self, room_id=None, path=None, user_id=None,
                             content=None):
        """ Stores data for a room under a given path.

        Args:
            room_id : The room to store the content under.
            path : The path which can be used to retrieve the data.
            user_id : If specified, verifies this user can store the data.
            content : The content to store.
        Raises:
            SynapseError if something went wrong.
        """
        if user_id:
            # check they are joined in the room
            yield _get_joined_or_throw(self.store,
                                      room_id=room_id,
                                      user_id=user_id)

        template = JSONTemplate({"topic": u"string"})
        template.check_json(content)

        # store in db
        yield self.store.store_path_data(room_id=room_id,
            path=path,
            content=json.dumps(content))

    @defer.inlineCallbacks
    def get_room_path_data(self, room_id=None, path=None, user_id=None,
                           public_room_rules=[],
                           private_room_rules=["join"]):
        """ Get path data from a room.

        Args:
            room_id : The room where the path data was stored.
            path : The path the data was stored under.
            user_id : If specified, verifies this user can access the path data
            in this room.
            public_room_rules : A list of membership states the user can be in,
            in order to read this data IN A PUBLIC ROOM. An empty list means
            'any state'.
            private_room_rules : A list of membership states the user can be in,
            in order to read this data IN A PRIVATE ROOM. An empty list means
            'any state'.
        Returns:
            The path data content.
        Raises:
            SynapseError if something went wrong.
        """
        # does this room exist
        room = yield self.store.get_room(room_id)
        if not room:
            raise RoomError(403, "Room does not exist.")
        room = room[0]

        # does this user exist in this room
        member = yield self.store.get_room_member(
                    room_id=room_id,
                    user_id=user_id)

        member_state = member[0].membership if member else None

        if room.is_public and public_room_rules:
            # make sure the user meets public room rules
            if member_state not in public_room_rules:
                raise RoomError(403, "Member does not meet public room rules.")
        elif not room.is_public and private_room_rules:
            # make sure the user meets private room rules
            if member_state not in private_room_rules:
                raise RoomError(403, "Member does not meet private room rules.")

        data = yield self.store.get_path_data(path)
        defer.returnValue(data)



@defer.inlineCallbacks
def _get_joined_or_throw(store=None, user_id=None, room_id=None):
    """Utility method to return the specified room member.

    Args:
        store : The event data store
        user_id : The member's ID
        room_id : The room where the member is joined.
    Returns:
        The room member.
    Raises:
        RoomError if this member does not exist/isn't joined.
    """
    member = yield store.get_room_member(
                        room_id=room_id,
                        user_id=user_id)
    if not member or member[0].membership != "join":
        raise RoomError(403, "")
    defer.returnValue(member)