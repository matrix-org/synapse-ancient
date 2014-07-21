# -*- coding: utf-8 -*-
"""Contains functions for registering clients."""
from twisted.internet import defer

from synapse.api.errors import RegistrationError
from . import BaseHandler
import synapse.util.stringutils as stringutils

import base64


class RegistrationHandler(BaseHandler):

    @defer.inlineCallbacks
    def register(self, user_id=None):
        """Registers a new client on the server.

        Args:
            user_id : The user ID to register with. If None, one will be
            randomly generated.
        Returns:
            A tuple of (user_id, access_token).
        Raises:
            RegistrationError if there was a problem registering.
        """

        if user_id:
            token = self._generate_token(user_id)
            yield self.store.register(user_id, token)
            defer.returnValue((user_id, token))
        else:
            # autogen a random user ID
            attempts = 0
            user_id = None
            token = None
            while not user_id and not token:
                try:
                    user_id = self._generate_user_id()
                    token = self._generate_token(user_id)
                    yield self.store.register(user_id, token)
                    defer.returnValue((user_id, token))
                except RegistrationError:
                    # if user id is taken, just generate another
                    user_id = None
                    token = None
                    attempts += 1
                    if attempts > 5:
                        raise RegistrationError(
                            500, "Cannot generate user ID.")

    def _generate_token(self, user_id):
        # urlsafe variant uses _ and - so use . as the separator and replace all
        # =s with .s so http clients don't quote =s when it is used as query
        # params.
        return (base64.urlsafe_b64encode(user_id).replace('=', '.') + '.' +
                stringutils.random_string(18))

    def _generate_user_id(self):
        return "-" + stringutils.random_string(18)
