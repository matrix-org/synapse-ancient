# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import StoreError

from ._base import SQLBaseStore


class ProfileStore(SQLBaseStore):

    def get_profile_displayname(self, user_localpart):
        return self._db_pool.runInteraction(self._get_profile_displayname,
                user_localpart)

    def _get_profile_displayname(self, txn, user_localpart):
        txn.execute("SELECT displayname FROM profiles WHERE user_id = ?",
                [user_localpart])

        row = txn.fetchone()
        if not row:
            raise StoreError(404, "No such user ID")

        return row[0]

    def set_profile_displayname(self, user_localpart, new_displayname):
        return self._db_pool.runInteraction(self._set_profile_displayname,
                user_localpart, new_displayname)

    def _set_profile_displayname(self, txn, user_localpart, new_displayname):
        txn.execute("UPDATE profiles SET displayname = ? WHERE user_id = ?",
                [new_displayname, user_localpart])
        if txn.rowcount == 0:
            raise StoreError(404, "No such user ID")
