# -*- coding: utf-8 -*-
from twisted.internet import defer

from sqlite3 import IntegrityError

from synapse.api.errors import StoreError

from ._base import SQLBaseStore

import time


class RegistrationStore(SQLBaseStore):

    def __init__(self, hs):
        super(RegistrationStore, self).__init__(hs)

    @defer.inlineCallbacks
    def register(self, user_id, token):
        """Attempts to register an account.

        Args:
            user_id (str): The desired user ID to register.
            token (str): The desired access token to use for this user.
        Raises:
            StoreError if the user_id could not be registered.
        """
        yield self._db_pool.runInteraction(self._register, user_id, token)

    def _register(self, txn, user_id, token):
        now = int(time.time())

        try:
            txn.execute("INSERT INTO users(name, creation_ts) VALUES (?,?)",
                        [user_id, now])
        except IntegrityError:
            raise StoreError(400, "User ID already taken.")

        # it's possible for this to get a conflict, but only for a single user
        # since tokens are namespaced based on their user ID
        txn.execute("INSERT INTO access_tokens(user_id, token) " +
                    "VALUES (?,?)", [txn.lastrowid, token])

    @defer.inlineCallbacks
    def get_user(self, token=None):
        """Get a user from the given access token.

        Args:
            token (str): The access token of a user.
        Returns:
            str: The user ID of the user.
        Raises:
            StoreError if no user was found.
        """
        user_id = yield self._db_pool.runInteraction(self._query_for_auth,
                    token)
        defer.returnValue(user_id)

    def _query_for_auth(self, txn, token):
        txn.execute("SELECT users.name FROM access_tokens LEFT JOIN users" +
                    " ON users.id = access_tokens.user_id WHERE token = ?",
                    token)
        row = txn.fetchone()
        if row:
            return row[0]

        raise StoreError(404, "Token not found.")