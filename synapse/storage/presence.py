# -*- coding: utf-8 -*-
from twisted.internet import defer

from ._base import SQLBaseStore


class PresenceStore(SQLBaseStore):
    def create_presence(self, user_localpart):
        return self._simple_insert(
            table="presence",
            values={"user_id": user_localpart},
        )

    def has_presence_state(self, user_localpart):
        return self._simple_select_one(
            table="presence",
            keyvalues={"user_id": user_localpart},
            retcols=["user_id"],
            allow_none=True,
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
            retcols=["state"],
        )

    def allow_presence_inbound(self, observed_localpart, observer_userid):
        return self._simple_insert(
                table="presence_allow_inbound",
                values={"observed_user_id": observed_localpart,
                        "observer_user_id": observer_userid},
        )

    def disallow_presence_inbound(self, observed_localpart, observer_userid):
        return self._simple_delete_one(
                table="presence_allow_inbound",
                keyvalues={"observed_user_id": observed_localpart,
                           "observer_user_id": observer_userid},
        )

    def is_presence_inbound_allowed(self, observed_localpart, observer_userid):
        return self._simple_select_one(
                table="presence_allow_inbound",
                keyvalues={"observed_user_id": observed_localpart,
                           "observer_user_id": observer_userid},
                allow_none=True,
        )

    def add_presence_list_pending(self, observer_localpart, observed_userid):
        return self._simple_insert(
                table="presence_list",
                values={"user_id": observer_localpart,
                        "observed_user_id": observed_userid,
                        "accepted": False},
        )

    def set_presence_list_accepted(self, observer_localpart, observed_userid):
        return self._simple_update_one(
                table="presence_list",
                keyvalues={"user_id": observer_localpart,
                           "observed_user_id": observed_userid},
                updatevalues={"accepted": True},
        )

    def get_presence_list(self, observer_localpart, accepted=None):
        keyvalues={"user_id": observer_localpart}
        if accepted is not None:
            keyvalues["accepted"] = accepted

        return self._simple_select_list(
                table="presence_list",
                keyvalues=keyvalues,
                retcols=["observed_user_id", "accepted"],
        )

    def del_presence_list(self, observer_localpart, observed_userid):
        return self._simple_delete_one(
                table="presence_list",
                keyvalues={"user_id": observer_localpart,
                           "observed_user_id": observed_userid},
        )
