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
            RoomError if something went wrong.
        """
        if user_id:
            # verify they are sending msgs under their own user id
            if global_msg.user_id != user_id:
                raise RoomError(403, "Must send messages as yourself.")

            # Check if sender_id is in room room_id
            yield _get_joined_or_throw(self.store,
                                      room_id=global_msg.room_id,
                                      user_id=global_msg.user_id)

        template = JSONTemplate({"msgtype": JSONTemplate.STR})
        template.check_json(content)

        # store message in db
        yield self.store.store_message(user_id=global_msg.user_id,
                                       room_id=global_msg.room_id,
                                       msg_id=global_msg.msg_id,
                                       content=json.dumps(content))


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