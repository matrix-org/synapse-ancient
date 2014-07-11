# -*- coding: utf-8 -*-
"""This module contains classes for authenticating the user."""
from twisted.internet import defer
from twisted.web.http import Request

from events.base import InvalidHttpRequestError
from synapse.util.dbutils import DbPool


class AccessTokenAuth(object):

    @staticmethod
    def defer_authenticate(func):
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
            for arg in args:
                if isinstance(arg, Request):
                    try:
                        userid = yield AccessTokenAuth._authenticate(arg)
                    except InvalidHttpRequestError as e:
                        defer.returnValue((e.get_status_code(),
                                           e.get_response_body()))
            kwargs["auth_user_id"] = userid
            result = yield func(*args, **kwargs)
            defer.returnValue(result)

        return defer_auth

    @staticmethod
    @defer.inlineCallbacks
    def _authenticate(request):
        """ Authenticates the user.

        Args:
            request - The HTTP request
        Returns:
            The user ID of the user.
        Raises:
            InvalidHttpRequestError if there is something wrong with the request
         """
        # get query parameters and check access_token
        try:
            user_id = yield DbPool.get().runInteraction(
                AccessTokenAuth._query_for_auth,
                request.args["access_token"])
            defer.returnValue(user_id)
        except KeyError:  # request has no access_token query param
            raise InvalidHttpRequestError(403, "No access_token")

    @classmethod
    def _query_for_auth(cls, txn, token):
        txn.execute("SELECT users.name FROM access_tokens LEFT JOIN users" +
                    " ON users.id = access_tokens.user_id WHERE token = ?",
                    token)
        row = txn.fetchone()
        if row:
            return row[0]

        raise InvalidHttpRequestError(403, "Unrecognised access token.")
