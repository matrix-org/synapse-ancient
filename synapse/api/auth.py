# -*- coding: utf-8 -*-
from twisted.internet import defer
from twisted.web.http import Request

from events import InvalidHttpRequestError

from functools import wraps


class AccessTokenAuth(object):

    @staticmethod
    def authenticate(func):
        """ A decorator for authenticating the user's access_token.

        The decorated function MUST have a twisted Request as an arg, which
        will then be checked via this decorator.

        If authed, this decorator will add the kwarg "auth_user_id" to the
        decorated function which will be the user ID for the supplied access
        token.
        '"""
        @wraps(func)
        def returned_wrapper(*args, **kwargs):
            for arg in args:
                if isinstance(arg, Request):
                    try:
                        userid = AccessTokenAuth._authenticate(arg)
                    except InvalidHttpRequestError as e:
                        # break early if auth failed
                        return (e.get_status_code(), e.get_response_body())
            kwargs["auth_user_id"] = userid
            return func(*args, **kwargs)
        return returned_wrapper

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
                        userid = AccessTokenAuth._authenticate(arg)
                    except InvalidHttpRequestError as e:
                        defer.returnValue((e.get_status_code(),
                                           e.get_response_body()))
            kwargs["auth_user_id"] = userid
            result = yield func(*args, **kwargs)
            defer.returnValue(result)

        return defer_auth

    @staticmethod
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
            token = request.args["access_token"]
            print "TODO: Auth token %s - returning userid b0b" % token
            return "b0b"
        except:
            raise InvalidHttpRequestError(403, "No access_token")