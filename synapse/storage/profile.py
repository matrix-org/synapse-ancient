# -*- coding: utf-8 -*-
from ._base import SQLBaseStore


class ProfileStore(SQLBaseStore):
    def create_profile(self, txn, user_localpart):
        return self._simple_insert(
            txn=txn,
            table="profiles",
            values={"user_id": user_localpart},
        )

    def get_profile_displayname(self, txn, user_localpart):
        return self._simple_select_one_onecol(
            txn=txn,
            table="profiles",
            keyvalues={"user_id": user_localpart},
            retcol="displayname",
        )

    def set_profile_displayname(self, txn, user_localpart, new_displayname):
        return self._simple_update_one(
            txn=txn,
            table="profiles",
            keyvalues={"user_id": user_localpart},
            updatevalues={"displayname": new_displayname},
        )

    def get_profile_avatar_url(self, txn, user_localpart):
        return self._simple_select_one_onecol(
            txn=txn,
            table="profiles",
            keyvalues={"user_id": user_localpart},
            retcol="avatar_url",
        )

    def set_profile_avatar_url(self, txn, user_localpart, new_avatar_url):
        return self._simple_update_one(
            txn=txn,
            table="profiles",
            keyvalues={"user_id": user_localpart},
            updatevalues={"avatar_url": new_avatar_url},
        )
