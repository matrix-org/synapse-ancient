# -*- coding: utf-8 -*-
"""Contains functions for registering clients."""
from twisted.internet import defer

from synapse.api.errors import CodeMessageException
import synapse.util.stringutils as stringutils

from sqlite3 import IntegrityError
import base64
import time


class RegistrationError(CodeMessageException):
    pass


class RegistrationEvent(object):

    def __init__(self, db_pool=None, user_id=None):
        self.db = db_pool
        self.desired_user_id = user_id

    @defer.inlineCallbacks
    def register(self):
        """Registers a new client on the server.

        Returns:
            A tuple of (user_id, access_token).
        Raises:
            RegistrationError if there was a problem registering.
        """

        if self.desired_user_id:
            (user_id, token) = yield self.db.runInteraction(
                    self._register,
                    self.desired_user_id)

            defer.returnValue((user_id, token))
        else:
            # autogen a random user ID
            (user_id, token) = (None, None)
            attempts = 0
            while not user_id and not token:
                try:
                    (user_id, token) = yield self.db.runInteraction(
                        self._register,
                        self._generate_user_id())
                except RegistrationError:
                    # if user id is taken, just generate another
                    attempts += 1
                    if attempts > 5:
                        raise RegistrationError(500, "Cannot generate user ID.")
            defer.returnValue((user_id, token))

    def _register(self, txn, user_id):
        now = int(time.time())

        try:
            txn.execute("INSERT INTO users(name, creation_ts) VALUES (?,?)",
                        [user_id, now])
        except IntegrityError:
            raise RegistrationError(400, "User ID already taken.")

        token = self._generate_token(user_id)

        # it's possible for this to get a conflict, but only for a single user
        # since tokens are namespaced based on their user ID
        txn.execute("INSERT INTO access_tokens(user_id, token) " +
                    "VALUES (?,?)", [txn.lastrowid, token])

        return (user_id, token)

    def _generate_token(cls, user_id):
        # urlsafe variant uses _ and - so use . as the separator and replace all
        # =s with .s so http clients don't quote =s when it is used as query
        # params.
        return (base64.urlsafe_b64encode(user_id).replace('=', '.') + '.' +
                 stringutils.random_string(18))

    def _generate_user_id(cls):
        return "-" + stringutils.random_string(18)
