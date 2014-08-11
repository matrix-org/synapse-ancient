# -*- coding: utf-8 -*-
from twisted.internet import defer

from ._base import BaseHandler
from synapse.api.errors import LoginError


class LoginHandler(BaseHandler):

    @defer.inlineCallbacks
    def login(self, user, password):
        # does this user exist, and if so, does the password hash match?
        raise LoginError(500, "Not implemented.")