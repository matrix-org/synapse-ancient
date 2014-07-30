# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError, AuthError
from synapse.api.constants import PresenceState

from ._base import BaseHandler


class PresenceHandler(BaseHandler):

    def __init__(self, hs):
        super(PresenceHandler, self).__init__(hs)

        self.homeserver = hs

        distributor = hs.get_distributor()
        distributor.observe("registered_user", self.registered_user)
        distributor.observe("received_edu", self._received_edu)

        self.federation = hs.get_replication_layer()

    def registered_user(self, user):
        self.store.create_presence(user.localpart)

    def _received_edu(self, origin, edu_type, content):
        hs = self.homeserver

        # TODO(paul): Maybe this suggests a nicer interface of
        #   federation.register_edu_handler("sy.presence_invite", callable...)

        if edu_type == "sy.presence_invite":
            return self.invite_presence(
                observed_user=hs.parse_userid(content["observed_user"]),
                observer_user=hs.parse_userid(content["observer_user"]),
            )
        elif edu_type == "sy.presence_accept":
            return self.accept_presence(
                observed_user=hs.parse_userid(content["observed_user"]),
                observer_user=hs.parse_userid(content["observer_user"]),
            )
        else:
            return defer.succeed(None)

    @defer.inlineCallbacks
    def get_state(self, target_user, auth_user):
        if target_user.is_mine:
            # TODO(paul): Only allow local users who are presence-subscribed
            state = yield self.store.get_presence_state(
                    target_user.localpart)

            defer.returnValue(state)
        else:
            # TODO(paul): Look up in local cache(?) or ask server-server API?
            defer.returnValue({"state": 0, "status_msg": ""})

    @defer.inlineCallbacks
    def set_state(self, target_user, auth_user, state):
        if not target_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        if target_user != auth_user:
            raise AuthError(400, "Cannot set another user's displayname")

        # TODO(paul): Sanity-check 'state'. Needs 'status' of suitable value
        # and optional status_msg.

        oldstate = yield self.store.set_presence_state(target_user.localpart,
                state
        )

        now_online = state["state"] != PresenceState.OFFLINE
        was_online = oldstate != PresenceState.OFFLINE

        if now_online and not was_online:
            self.start_polling_presence(target_user)
        elif not now_online and was_online:
            self.stop_polling_presence(target_user)

    @defer.inlineCallbacks
    def send_invite(self, observer_user, observed_user):
        if not observer_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        yield self.store.add_presence_list_pending(
                observer_user.localpart, observed_user.to_string())

        if observed_user.is_mine:
            yield self.invite_presence(observed_user, observer_user)
        else:
            yield self.federation.send_edu(
                    destination=observed_user.domain,
                    edu_type="sy.presence_invite",
                    content={
                        "observed_user": observed_user.to_string(),
                        "observer_user": observer_user.to_string(),
                    })

    @defer.inlineCallbacks
    def invite_presence(self, observed_user, observer_user):
        # TODO(paul): Eventually we'll ask the user's permission for this
        # before accepting. For now just accept any invite request
        yield self.store.allow_presence_inbound(
                observed_user.localpart, observer_user.to_string())

        if observer_user.is_mine:
            yield self.accept_presence(observed_user, observer_user)
        else:
            yield self.federation.send_edu(
                    destination=observer_user.domain,
                    edu_type="sy.presence_accept",
                    content={
                        "observed_user": observed_user.to_string(),
                        "observer_user": observer_user.to_string(),
                    })

    @defer.inlineCallbacks
    def accept_presence(self, observed_user, observer_user):
        yield self.store.set_presence_list_accepted(
                observer_user.localpart, observed_user.to_string())

        self.start_polling_presence(observer_user, target_user=observed_user)

    def start_polling_presence(self, user, target_user=None):
        # TODO(paul)
        pass

    def stop_polling_presence(self, user, target_user=None):
        # TODO(paul)
        pass
