# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer
from twisted.web.http import Request

from events.base import InvalidHttpRequestError
from synapse.util.dbutils import DbPool


class Auth(object):

    mod_registered_user = None
    """A RegisteredUserModule."""

    @classmethod
    def defer_registered_user(cls, func):
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
                        userid = yield cls.mod_registered_user.get_user_by_req(arg)
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


class RegisteredUserModule(object):

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
