# -*- coding: utf-8 -*-
"""Contains functions for performing events on rooms."""
from twisted.internet import defer

from synapse.api.constants import Membership
from synapse.api.errors import RoomError
from synapse.api.storage import StoreException
from synapse.api.events.room import RoomTopicEvent, MessageEvent
from . import BaseHandler

import json
import time


class MessageHandler(BaseHandler):

    @defer.inlineCallbacks
    def get_message(self, event=None):
        """ Retrieve a message.

        Args:
            event : A message event.
        Returns:
            The message, or None if no message exists.
        Raises:
            SynapseError if something went wrong.
        """
        yield self.auth.check(event, raises=True)

        # Pull out the message from the db
        results = yield self.store.get_message(room_id=event.room_id,
                                               msg_id=event.msg_id,
                                               user_id=event.user_id)

        if results:
            defer.returnValue(results[0])
        defer.returnValue(None)

    @defer.inlineCallbacks
    def send_message(self, event=None):
        """ Send a message.

        Args:
            event : The message event to store.
        Raises:
            SynapseError if something went wrong.
        """
        yield self.auth.check(event, raises=True)

        if hasattr(event, "auth_user_id"):
            # verify they are sending msgs under their own user id
            if event.user_id != event.auth_user_id:
                raise RoomError(403, "Must send messages as yourself.")

        # store message in db
        yield self.store.store_message(user_id=event.user_id,
                                       room_id=event.room_id,
                                       msg_id=event.msg_id,
                                       content=json.dumps(event.content))

    @defer.inlineCallbacks
    def store_room_path_data(self, event=None, path=None):
        """ Stores data for a room under a given path.

        Args:
            event : The room path event
            path : The path which can be used to retrieve the data.
        Raises:
            SynapseError if something went wrong.
        """
        yield self.auth.check(event, raises=True)

        # store in db
        yield self.store.store_path_data(room_id=event.room_id,
                                         path=path,
                                         content=json.dumps(event.content))

    @defer.inlineCallbacks
    def get_room_path_data(self, event=None, path=None,
                           public_room_rules=[],
                           private_room_rules=["join"]):
        """ Get path data from a room.

        Args:
            event : The room path event
            path : The path the data was stored under.
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
        if event.type == RoomTopicEvent.TYPE:
            # anyone invited/joined can read the topic
            private_room_rules = ["invite", "join"]

        # does this room exist
        room = yield self.store.get_room(event.room_id)
        if not room:
            raise RoomError(403, "Room does not exist.")
        room = room[0]

        # does this user exist in this room
        member = yield self.store.get_room_member(
            room_id=event.room_id,
            user_id="" if not event.auth_user_id else event.auth_user_id)

        member_state = member[0].membership if member else None

        if room.is_public and public_room_rules:
            # make sure the user meets public room rules
            if member_state not in public_room_rules:
                raise RoomError(403, "Member does not meet public room rules.")
        elif not room.is_public and private_room_rules:
            # make sure the user meets private room rules
            if member_state not in private_room_rules:
                raise RoomError(
                    403, "Member does not meet private room rules.")

        data = yield self.store.get_path_data(path)
        defer.returnValue(data)


class RoomCreationHandler(BaseHandler):

    @defer.inlineCallbacks
    def create_room(self, user_id=None, room_id=None, config=None):
        """ Creates a new room.

        Args:
            user_id (str): The ID of the user creating the new room.
            room_id (str): The proposed ID for the new room. Can be None, in
            which case one will be created for you.
            config (dict) : A dict of configuration options.
        Returns:
            The new room ID.
        Raises:
            RoomError if the room ID was taken, couldn't be stored, or something
            went horribly wrong.
        """
        try:
            new_room_id = yield self.store.store_room(
                room_id=room_id,
                room_creator_user_id=user_id,
                is_public=config["visibility"] == "public"
            )
            if not new_room_id:
                raise RoomError(409, "Room ID in use.")

            defer.returnValue(new_room_id)
        except StoreException:
            raise RoomError(500, "Unable to create room.")


class RoomMemberHandler(BaseHandler):

    @defer.inlineCallbacks
    def get_room_member(self, event=None):
        """Retrieve a room member from a room.

        Args:
            event : The room member event
        Returns:
            The room member, or None if this member does not exist.
        Raises:
            SynapseError if something goes wrong.
        """
        yield self.auth.check(event, raises=True)

        member = yield self.store.get_room_member(user_id=event.user_id,
                                                  room_id=event.room_id)
        if member:
            defer.returnValue(member[0])
        defer.returnValue(member)

    @defer.inlineCallbacks
    def change_membership(self, event=None, broadcast_msg=False):
        """ Change the membership status of a user in a room.

        Args:
            event (SynapseEvent): The membership event
            broadcast_msg (bool): True to inject a membership message into this
            room on success.
        Raises:
            SynapseError if there was a problem changing the membership.
        """
        yield self.auth.check(event, raises=True)

        # store membership
        yield self.store.store_room_member(
            user_id=event.user_id,
            room_id=event.room_id,
            content=event.content,
            membership=event.membership)

        if broadcast_msg:
            yield self._inject_membership_msg(
                source=event.auth_user_id,
                target=event.user_id,
                room_id=event.room_id,
                membership=event.membership)

    @defer.inlineCallbacks
    def _inject_membership_msg(self, room_id=None, source=None, target=None,
                               membership=None):
        # TODO this should be a different type of message, not sy.text
        if membership == Membership.INVITE:
            body = "%s invited %s to the room." % (source, target)
        elif membership == Membership.JOIN:
            body = "%s joined the room." % (target)
        elif membership == Membership.LEAVE:
            body = "%s left the room." % (target)
        else:
            raise RoomError(500, "Unknown membership value %s" % membership)

        membership_json = {
            "msgtype": u"sy.text",
            "body": body
        }
        msg_id = "m%s" % int(time.time())

        event = self.event_factory.create_event(
                etype=MessageEvent.TYPE,
                room_id=room_id,
                user_id="_hs_",
                msg_id=msg_id,
                content=membership_json
                )

        handler = MessageHandler(
            ev_factory=self.event_factory,
            store=self.store,
            auth=self.auth)
        yield handler.send_message(event)
