# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer

from synapse.api.errors import AuthError
from synapse.rest.base import InvalidHttpRequestError
from synapse.util.dbutils import DbPool


class Auth(object):

    def __init__(self, mod_token=None, mod_registered_user=None, mod_room=None):
        self.mod_token = mod_token
        self.mod_room = mod_room
        self.mod_registered_user = mod_registered_user

    def check(self, event, raises=False):
        """ Checks if this event is correctly authed.

        What this does depends on the event fields, according to the following:
            auth_user_id : Checks this user ID is a registered user.
            auth_room_id : Checks that auth_user_id can perform this action
            in the given room. This will vary depending on numerous factors like
            whether the room is a public room or not.
        Returns:
            True if auth checks pass.
        Raises:
            AuthError if there was a problem authorising this event. This will
            be raised only if raises=True.
        """
        try:
            # check auth_user_id
            if self.mod_registered_user:
                try:
                    self.mod_registered_user.check(user_id=event.auth_user_id)
                except AttributeError:
                    pass

            # check auth_room_id
            if self.mod_room:
                try:
                    self.mod_room.check(
                        user_id=event.auth_user_id,
                        room_id=event.auth_room_id)
                except AttributeError:
                    pass

            return True
        except AuthError as e:
            if raises:
                raise e
        return False


class AccessTokenModule(object):

    def __init__(self, data_store):
        self.data_store = data_store

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
            raise InvalidHttpRequestError(403, "Missing access token.")

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

        raise InvalidHttpRequestError(403, "Unrecognised access token.")


class AuthModule(object):

    """An interface for an AuthModule. These modules must be able to check
    an event for whatever it is they are authing."""

    def check(event):
        raise NotImplementedError()


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
                        userid = yield cls.auth.mod_token.get_user_by_req(arg)
                    except InvalidHttpRequestError as e:
                        defer.returnValue((e.get_status_code(),
                                           e.get_response_body()))
            # should have a userid now, or should've thrown by now.
            if not userid:
                raise RuntimeError("Decorated function didn't have a twisted " +
                                   "Request as an arg.")

            kwargs["auth_user_id"] = userid
            result = yield func(*args, **kwargs)
            defer.returnValue(result)

        return defer_auth
