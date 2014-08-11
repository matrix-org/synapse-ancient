# -*- coding: utf-8 -*-
from twisted.internet import defer

from ._base import BaseHandler
from synapse.api.errors import LoginError

import bcrypt


class LoginHandler(BaseHandler):

    @defer.inlineCallbacks
    def login(self, user, password):
        # pull out the hash for this user if they exist
        user_info = self.store.get_user_by_id(user_id=user)
        print user_info
        # check the hash
        raise LoginError(500, "Not implemented.")