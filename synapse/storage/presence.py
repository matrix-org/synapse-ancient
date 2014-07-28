# -*- coding: utf-8 -*-
from twisted.internet import defer

from ._base import SQLBaseStore


class PresenceStore(SQLBaseStore):
    def create_presence(self, user_localpart):
        return self._simple_insert(
            table="presence",
            values={"user_id": user_localpart},
        )

    def get_presence_state(self, user_localpart):
        return self._simple_select_one(
            table="presence",
            keyvalues={"user_id": user_localpart},
            retcols=["state", "status_msg"],
        )

    def set_presence_state(self, user_localpart, new_state, new_msg):
        return self._simple_update_one(
            table="presence",
            keyvalues={"user_id": user_localpart},
            updatevalues={"state": new_state, "status_msg": new_msg},
        )
