# -*- coding: utf-8 -*-
"""Contains functions for performing events on rooms."""
from twisted.internet import defer

from synapse.api.constants import Membership
from synapse.api.errors import RoomError, StoreError
from synapse.api.events.room import RoomTopicEvent, MessageEvent
from synapse.util import stringutils
from . import BaseHandler

import json
import time


class MessageHandler(BaseHandler):

    @defer.inlineCallbacks
    def get_message(self, msg_id=None, room_id=None, sender_id=None,
                    user_id=None):
        """ Retrieve a message.

        Args:
            msg_id (str): The message ID to obtain.
            room_id (str): The room where the message resides.
            sender_id (str): The user ID of the user who sent the message.
            user_id (str): The user ID of the user making this request.
        Returns:
            The message, or None if no message exists.
        Raises:
            SynapseError if something went wrong.
        """
        yield self.auth.check_joined_room(room_id, user_id)

        # Pull out the message from the db
        msg = yield self.store.get_message(room_id=room_id,
                                               msg_id=msg_id,
                                               user_id=sender_id)

        if msg:
            defer.returnValue(msg)
        defer.returnValue(None)

    @defer.inlineCallbacks
    def send_message(self, event=None, suppress_auth=False):
        """ Send a message.

        Args:
            event : The message event to store.
            suppress_auth (bool) : True to suppress auth for this message. This
            is primarily so the home server can inject messages into rooms at
            will.
        Raises:
            SynapseError if something went wrong.
        """
        with (yield self.room_lock.lock(event.room_id)):
            if not suppress_auth:
                yield self.auth.check(event, raises=True)

            # store message in db
            store_id = yield self.store.store_message(user_id=event.user_id,
                                           room_id=event.room_id,
                                           msg_id=event.msg_id,
                                           content=json.dumps(event.content))

            yield self.hs.get_federation().handle_new_event(event)

            self.notifier.on_new_event(event, store_id)

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
    def get_room_path_data(self, user_id=None, room_id=None, path=None,
                           event_type=None,
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
        if event_type == RoomTopicEvent.TYPE:
            # anyone invited/joined can read the topic
            private_room_rules = ["invite", "join"]

        # does this room exist
        room = yield self.store.get_room(room_id)
        if not room:
            raise RoomError(403, "Room does not exist.")

        # does this user exist in this room
        member = yield self.store.get_room_member(
            room_id=room_id,
            user_id="" if not user_id else user_id)

        member_state = member.membership if member else None

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
            SynapseError if the room ID was taken, couldn't be stored, or
            something went horribly wrong.
        """
        if room_id:
            yield self.store.store_room_and_member(
                room_id=room_id,
                room_creator_user_id=user_id,
                is_public=config["visibility"] == "public"
            )
            defer.returnValue(room_id)
        else:
            # autogen room IDs and try to create it. We may clash, so just
            # try a few times till one goes through, giving up eventually.
            attempts = 0
            while attempts < 5:
                try:
                    gen_room_id = stringutils.random_string(18)
                    yield self.store.store_room_and_member(
                        room_id=gen_room_id,
                        room_creator_user_id=user_id,
                        is_public=config["visibility"] == "public"
                    )
                    defer.returnValue(gen_room_id)
                except StoreError:
                    attempts += 1
            raise StoreError(500, "Couldn't generate a room ID.")


class RoomMemberHandler(BaseHandler):

    def __init__(self, hs):
        super(RoomMemberHandler, self).__init__(hs)
        self.msg_handler = (hs.get_event_handler_factory().message_handler())

    @defer.inlineCallbacks
    def get_room_members(self, room_id=None, user_id=None, limit=0,
                         start_tok=None, end_tok=None):
        """Retrieve a list of room members in the room.

        Args:
            room_id (str): The room to get the member list for.
            user_id (str): The ID of the user making the request.
            limit (int): The max number of members to return.
            start_tok (str): Optional. The start token if known.
            end_tok (str): Optional. The end token if known.
        Returns:
            dict: A filter streamable dict.
        Raises:
            SynapseError if something goes wrong.
        """
        yield self.auth.check_joined_room(room_id, user_id)

        member_list = yield self.store.get_room_members(room_id=room_id)
        event_list = self.store.to_events(member_list)
        chunk_data = {
            "start": "NOT_IMPLEMENTED",
            "end": "NOT_IMPLEMENTED",
            "chunk": event_list
        }
        # TODO honor filter stream params
        # TODO snapshot this list to return on subsequent requests when
        # paginating
        defer.returnValue(chunk_data)

    @defer.inlineCallbacks
    def get_room_member(self, room_id, member_user_id, auth_user_id):
        """Retrieve a room member from a room.

        Args:
            room_id : The room the member is in.
            member_user_id : The member's user ID
            auth_user_id : The user ID of the user making this request.
        Returns:
            The room member, or None if this member does not exist.
        Raises:
            SynapseError if something goes wrong.
        """
        yield self.auth.check_joined_room(room_id, auth_user_id)

        member = yield self.store.get_room_member(user_id=member_user_id,
                                                  room_id=room_id)
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
            user_id=event.target_user_id,
            room_id=event.room_id,
            content=event.content,
            membership=event.content["membership"])

        if broadcast_msg:
            yield self._inject_membership_msg(
                source=event.user_id,
                target=event.target_user_id,
                room_id=event.room_id,
                membership=event.content["membership"])

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
                user_id="_homeserver_",
                msg_id=msg_id,
                content=membership_json
                )

        yield self.msg_handler.send_message(event, suppress_auth=True)
