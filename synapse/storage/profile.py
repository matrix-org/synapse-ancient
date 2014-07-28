# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import StoreError

from ._base import SQLBaseStore


class ProfileStore(SQLBaseStore):
    def create_profile(self, user_localpart):
        return self.interact_simple_insert(
            table="profiles",
            values={"user_id": user_localpart},
        )

    def get_profile_displayname(self, user_localpart):
        return self.interact_simple_select_one_onecol(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            retcol="displayname",
        )

    def set_profile_displayname(self, user_localpart, new_displayname):
        return self.interact_simple_update_one(
            table="profiles",
            keyvalues={"user_id": user_localpart},
            updatevalues={"displayname": new_displayname},
        )
