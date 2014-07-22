# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer

from synapse.api.constants import Membership
from synapse.api.errors import AuthError, StoreError
from synapse.api.events.room import (RoomTopicEvent, RoomMemberEvent,
                                     MessageEvent)

import logging

logger = logging.getLogger(__name__)


class Auth(object):

    def __init__(self, store):
        self.store = store

    @defer.inlineCallbacks
    def check(self, event, raises=False):
        """ Checks if this event is correctly authed.

        Returns:
            True if the auth checks pass.
        Raises:
            AuthError if there was a problem authorising this event. This will
            be raised only if raises=True.
        """
        try:
            if event.type in [RoomTopicEvent.TYPE, MessageEvent.TYPE]:
                yield self.check_joined_room(event.room_id, event.user_id)
                defer.returnValue(True)
            elif event.type == RoomMemberEvent.TYPE:
                allowed = yield self.is_membership_change_allowed(event)
                defer.returnValue(allowed)
            else:
                raise AuthError(500, "Unknown event type %s" % event.type)
        except AuthError as e:
            logger.info("Even auth check failed on event %s with msg: %s" %
                        (event, e.msg))
            if raises:
                raise e
        defer.returnValue(False)

    @defer.inlineCallbacks
    def check_joined_room(self, room_id, user_id):
        try:
            member = yield self.store.get_room_member(
                        room_id=room_id,
                        user_id=user_id)
            if not member or member[0].membership != Membership.JOIN:
                raise AuthError(403, "User %s not in room %s" %
                                (user_id, room_id))
            defer.returnValue(member)
        except AttributeError:
            pass
        defer.returnValue(None)

    @defer.inlineCallbacks
    def is_membership_change_allowed(self, event):
        # does this room even exist
        room = self.store.get_room(event.room_id)
        if not room:
            raise AuthError(403, "Room does not exist")

        # get info about the caller
        try:
            caller = yield self.store.get_room_member(
                user_id=event.user_id,
                room_id=event.room_id)
        except:
            caller = None
        caller_in_room = caller and caller[0].membership == "join"

        # get info about the target
        try:
            target = yield self.store.get_room_member(
                user_id=event.target_user_id,
                room_id=event.room_id)
        except:
            target = None
        target_in_room = target and target[0].membership == "join"

        if not event.membership:
            # not a membership change, but a request for one. They can only do
            # that if they are in the room.
            defer.returnValue(caller_in_room)

        if Membership.INVITE == event.membership:
            # Invites are valid iff caller is in the room and target isn't.
            if not caller_in_room or target_in_room:
                # caller isn't joined or the target is already in the room.
                raise AuthError(403, "Cannot invite.")
        elif Membership.JOIN == event.membership:
            # Joins are valid iff caller == target and they were:
            # invited: They are accepting the invitation
            # joined: It's a NOOP
            if (event.user_id != event.target_user_id or not caller or
                    caller[0].membership not in
                    [Membership.INVITE, Membership.JOIN]):
                raise AuthError(403, "You are not invited to this room.")
        elif Membership.LEAVE == event.membership:
            if not caller_in_room or event.target_user_id != event.user_id:
                # trying to leave a room you aren't joined or trying to force
                # another user to leave
                raise AuthError(403, "Cannot leave.")
        else:
            raise AuthError(500, "Unknown membership %s" % event.membership)

        defer.returnValue(True)

    def get_user_by_req(self, request):
        """ Get a registered user's ID.

        Args:
            request - An HTTP request with an access_token query parameter.
        Returns:
            str: The user ID of the user who has that access token.
        Raises:
            AuthError if no user by that token exists or the token is invalid.
        """
        # Can optionally look elsewhere in the request (e.g. headers)
        try:
            return self.get_user_by_token(request.args["access_token"])
        except KeyError:
            raise AuthError(403, "Missing access token.")

    @defer.inlineCallbacks
    def get_user_by_token(self, token):
        """ Get a registered user's ID.

        Args:
            token (str)- The access token to get the user by.
        Returns:
            str: The user ID of the user who has that access token.
        Raises:
            AuthError if no user by that token exists or the token is invalid.
        """
        try:
            user_id = yield self.store.get_user(token=token)
            defer.returnValue(user_id)
        except StoreError:
            raise AuthError(403, "Unrecognised access token.")



