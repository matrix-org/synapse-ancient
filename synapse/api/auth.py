# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer

from synapse.api.constants import Membership
from synapse.api.errors import AuthError, StoreError
from synapse.api.events.room import (RoomTopicEvent, RoomMemberEvent,
                                     MessageEvent)

import logging

logger = logging.getLogger(__name__)


class AuthModule(object):

    """An interface for an AuthModule. These modules must be able to check
    an event for whatever it is they are authing. They MUST have a 'NAME'
    attribute in order to be linked with an Auth instance."""

    def check(event):
        """Check if this event needs to be authed and perform the auth.

        Args:
            event (SynapseEvent): An event to auth.
        Returns:
            Optional, depending on the implementation. For example, an access
            token module may want to return the user ID.
        Raises:
            AuthError iff the auth check fails, NOT if there are missing fields.
        """
        raise NotImplementedError()


class Auth(object):

    def __init__(self, *args):
        """Construct a new Auth instance with the specified AuthModules.

        Args:
            *args (AuthModule): The modules to use when authing.
        """
        self.modules = {}
        for module in args:
            self.modules[module.NAME] = module

    def get_mod(self, mod_name):
        """Return a module by name.

        Args:
            mod_name (str): The name of the module to obtain.
        Returns:
            The AuthModule or None.
        """
        try:
            return self.modules[mod_name]
        except KeyError:
            pass
        return None

    @defer.inlineCallbacks
    def check(self, event, raises=False):
        """ Checks if this event is correctly authed.

        What this does depends on the modules attached. Each module will be
        passed this event and will have the option of checking it.

        Returns:
            True if the auth checks pass.
        Raises:
            AuthError if there was a problem authorising this event. This will
            be raised only if raises=True.
        """
        try:
            for module in self.modules.values():
                yield module.check(event)

            defer.returnValue(True)
        except AuthError as e:
            logger.info("[%s] Failed on event %s with msg: %s" %
                        (module.NAME, event, e.msg))
            if raises:
                raise e
        defer.returnValue(False)


class JoinedRoomModule(AuthModule):
    NAME = "mod_joined_room"

    def __init__(self, store):
        super(JoinedRoomModule, self).__init__()
        self.store = store

    @defer.inlineCallbacks
    def check(self, event):

        if event.type not in [RoomTopicEvent.TYPE, RoomMemberEvent.TYPE,
                              MessageEvent.TYPE]:
            defer.returnValue(None)

        # ignore membership change requests, another module will handle that
        if event.type == RoomMemberEvent.TYPE and event.membership:
            defer.returnValue(None)

        if not hasattr(event, "auth_user_id"):
            defer.returnValue(None)

        try:
            member = yield self.store.get_room_member(
                        room_id=event.room_id,
                        user_id=event.auth_user_id)
            if not member or member[0].membership != Membership.JOIN:
                raise AuthError(403, JoinedRoomModule.NAME)
            defer.returnValue(member)
        except AttributeError:
            pass
        defer.returnValue(None)


class MembershipChangeModule(AuthModule):
    NAME = "mod_membership_change"

    def __init__(self, store):
        super(MembershipChangeModule, self).__init__()
        self.store = store

    @defer.inlineCallbacks
    def check(self, event):
        if event.type is not RoomMemberEvent.TYPE:
            defer.returnValue(None)

        if not hasattr(event, "auth_user_id"):
            defer.returnValue(True)

        # does this room even exist
        room = self.store.get_room(event.room_id)
        if not room:
            raise AuthError(403, "Room does not exist")

        # get info about the caller
        try:
            caller = yield self.store.get_room_member(
                user_id=event.auth_user_id,
                room_id=event.room_id)
        except:
            caller = None
        caller_in_room = caller and caller[0].membership == "join"

        # get info about the target
        try:
            target = yield self.store.get_room_member(
                user_id=event.user_id,
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
            if (event.auth_user_id != event.user_id or not caller or
                    caller[0].membership not in
                    [Membership.INVITE, Membership.JOIN]):
                raise AuthError(403, "Cannot join.")
        elif Membership.LEAVE == event.membership:
            if not caller_in_room or event.user_id != event.auth_user_id:
                # trying to leave a room you aren't joined or trying to force
                # another user to leave
                raise AuthError(403, "Cannot leave.")
        else:
            raise AuthError(500, "Unknown membership %s" % event.membership)

        defer.returnValue(True)


class AccessTokenModule(AuthModule):
    NAME = "mod_token"

    def __init__(self, store):
        self.store = store

    @defer.inlineCallbacks
    def check(self, event):
        """Checks for an 'auth_token' attribute and auths it."""
        try:
            user_id = yield self.get_user_by_token(event.auth_token)
            defer.returnValue(user_id)
        except AttributeError:
            pass
        defer.returnValue(None)

    def get_user_by_req(self, request):
        """ Get a registered user's ID.

        Args:
            request - An HTTP request with an access_token query parameter.
        Returns:
            The user ID of the user who has that access token.
        Raises:
            InvalidHttpRequestError if no user by that token exists.
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
            token - The access token to get the user by.
        Returns:
            The user ID of the user who has that access token.
        Raises:
            InvalidHttpRequestError if no user by that token exists.
        """
        try:
            user_id = yield self.store.get_user(token=token)
            defer.returnValue(user_id)
        except StoreError:
            raise AuthError(403, "Unrecognised access token.")



