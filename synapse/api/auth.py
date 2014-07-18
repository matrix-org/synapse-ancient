# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer

from synapse.api.constants import Membership
from synapse.api.errors import AuthError
from synapse.util.dbutils import DbPool

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
        """Checks if auth_user_id is joined in the room room_id."""

        try:
            # TODO this is horrible, this shouldn't care about event.membership.
            if (event.auth_user_id and event.room_id and
                                            not hasattr(event, "membership")):

                room = yield self.store.get_room(event.room_id)
                if not room:
                    raise AuthError(403, "Room does not exist")

                has_joined = yield self.has_joined_room(
                    event.auth_user_id, event.room_id
                )

                if not has_joined:
                    raise AuthError(403, JoinedRoomModule.NAME)
                defer.returnValue(has_joined)
        except AttributeError:
            pass
        defer.returnValue(None)

    @defer.inlineCallbacks
    def has_joined_room(self, user_id, room_id):
        try:
            member = yield self.store.get_room_member(
                        room_id=room_id,
                        user_id=user_id)
            if not member or member[0].membership != "join":
                defer.returnValue(False)
            defer.returnValue(True)
        except AttributeError:
            pass
        defer.returnValue(False)


class MembershipChangeModule(AuthModule):
    NAME = "mod_membership_change"

    def __init__(self, store):
        super(MembershipChangeModule, self).__init__()
        self.store = store

    @defer.inlineCallbacks
    def check(self, event):
        """Checks if this membership change is allowed to take place. Looks for
        the keys 'membership' (the action), 'auth_user_id' (the initiator), and
        'user_id' (the target).
        """
        try:
            if (not event.auth_user_id or not event.sender or not
                event.membership or not event.room_id):
                raise AttributeError()
        except AttributeError:
            defer.returnValue(False)

        # does this room even exist
        room = yield self.store.get_room(event.room_id)
        if not room:
            raise AuthError(403, "Room does not exist")

        # get info about the caller
        try:
            caller = yield self.store.get_room_member(
                user_id=event.auth_user_id,
                room_id=event.room_id)
        except:
            pass
        caller_in_room = caller and caller[0].membership == "join"

        # get info about the target
        try:
            target = yield self.store.get_room_member(
                user_id=event.target_user,
                room_id=event.room_id)
        except:
            pass
        target_in_room = target and target[0].membership == "join"

        if Membership.INVITE == event.membership:
            # Invites are valid iff caller is in the room and target isn't.
            if not caller_in_room or target_in_room:
                # caller isn't joined or the target is already in the room.
                raise AuthError(403, "Cannot invite.")
        elif Membership.JOIN == event.membership:
            # Joins are valid iff caller == target and they were:
            # invited: They are accepting the invitation
            # joined: It's a NOOP
            if (event.auth_user_id != event.target_user or not caller or
                    caller[0].membership not in
                    [Membership.INVITE, Membership.JOIN]):
                raise AuthError(403, "Cannot join.")
        elif Membership.LEAVE == event.membership:
            if not caller_in_room or event.target_user != event.auth_user_id:
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
        # TODO use self.data_store
        user_id = yield DbPool.get().runInteraction(
            self._query_for_auth,
            token)
        defer.returnValue(user_id)

    def _query_for_auth(self, txn, token):
        txn.execute("SELECT users.name FROM access_tokens LEFT JOIN users" +
                    " ON users.id = access_tokens.user_id WHERE token = ?",
                    token)
        row = txn.fetchone()
        if row:
            return row[0]

        raise AuthError(403, "Unrecognised access token.")


class AuthDecorator(object):

    """A class which contains methods which can be invoked as decorators. The
    auth mechanism used is defined by the class attribute 'auth'.
    """

    auth = None
    """The Auth instance to use."""

    @classmethod
    def defer_verify_token(cls, func):
        """ A decorator for authenticating the user's access_token.

        The decorated function MUST have a twisted Request as an arg, which
        will then be checked via this decorator.

        If authed, this decorator will add the kwarg "auth_user_id" to the
        decorated function which will be the user ID for the supplied access
        token.

        This is the deferred version to work with @defer.inlineCallbacks.
        '"""
        @defer.inlineCallbacks
        def defer_auth(*args, **kwargs):
            userid = None
            for arg in args:
                # if it has request headers and query params, it's probably it
                if hasattr(arg, "requestHeaders") and hasattr(arg, "args"):
                    try:
                        userid = yield (cls.auth.get_mod(
                            AccessTokenModule.NAME).get_user_by_req(arg))
                    except AuthError as e:
                        defer.returnValue((e.code, e.msg))
            # should have a userid now, or should've thrown by now.
            if not userid:
                raise RuntimeError("Decorated function didn't have a twisted " +
                                   "Request as an arg.")

            kwargs["auth_user_id"] = userid
            result = yield func(*args, **kwargs)
            defer.returnValue(result)

        return defer_auth
