# -*- coding: utf-8 -*-
"""Contains functions for registering clients."""
from twisted.internet import defer

from synapse.types import UserID
from synapse.api.errors import SynapseError, RegistrationError
from ._base import BaseHandler
import synapse.util.stringutils as stringutils

import base64


class RegistrationHandler(BaseHandler):

    def __init__(self, hs):
        super(RegistrationHandler, self).__init__(hs)

        self.distributor = hs.get_distributor()
        self.distributor.declare("registered_user")

    @defer.inlineCallbacks
    def register(self, localpart=None):
        """Registers a new client on the server.

        Args:
            localpart : The local part of the user ID to register. If None,
              one will be randomly generated.
        Returns:
            A tuple of (user_id, access_token).
        Raises:
            RegistrationError if there was a problem registering.
        """

        if localpart:
            user = UserID(localpart, self.hs.hostname, True)
            user_id = user.to_string()

            token = self._generate_token(user_id)
            yield self.store.register(user_id, token)

            self.distributor.fire("registered_user", user)
            defer.returnValue((user_id, token))
        else:
            # autogen a random user ID
            attempts = 0
            user_id = None
            token = None
            while not user_id and not token:
                try:
                    localpart = self._generate_user_id()
                    user = UserID(localpart, self.hs.hostname, True)
                    user_id = user.to_string()

                    token = self._generate_token(user_id)
                    yield self.store.register(user_id, token)

                    self.distributor.fire("registered_user", user)
                    defer.returnValue((user_id, token))
                except SynapseError:
                    # if user id is taken, just generate another
                    user_id = None
                    token = None
                    attempts += 1
                    if attempts > 5:
                        raise RegistrationError(
                            500, "Cannot generate user ID.")

    def _generate_token(self, user_id):
        # urlsafe variant uses _ and - so use . as the separator and replace
        # all =s with .s so http clients don't quote =s when it is used as
        # query params.
        return (base64.urlsafe_b64encode(user_id).replace('=', '.') + '.' +
                stringutils.random_string(18))

    def _generate_user_id(self):
        return "-" + stringutils.random_string(18)
