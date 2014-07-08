# -*- coding: utf-8 -*-
from twisted.internet import defer
from twisted.web.http import Request


class AccessTokenAuth(object):

    @staticmethod
    def authenticate(func):
        def auth(*args, **kwargs):
            for arg in args:
                if isinstance(arg, Request):
                    result = AccessTokenAuth._authenticate(arg)
                    if result:
                        return result
            return func(*args, **kwargs)

        return auth

    @staticmethod
    def deferAuthenticate(func):  # follow twisted's naming scheme
        @defer.inlineCallbacks
        def defer_auth(*args, **kwargs):
            for arg in args:
                if isinstance(arg, Request):
                    result = AccessTokenAuth._authenticate(arg)
                    if result:
                        defer.returnValue(result)
            result = yield func(*args, **kwargs)
            defer.returnValue(result)

        return defer_auth

    @staticmethod
    def _authenticate(request):
        # get query parameters and check access_token
        try:
            token = request.args["access_token"]
            print "Token %s" % token
        except:
            return (403, "No access_token")