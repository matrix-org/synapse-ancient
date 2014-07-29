# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError, AuthError

from ._base import BaseHandler


class PresenceHandler(BaseHandler):

    def __init__(self, hs):
        super(PresenceHandler, self).__init__(hs)

        distributor = hs.get_distributor()
        distributor.observe("registered_user", self.registered_user)

    def registered_user(self, user):
        self.store.create_presence(user.localpart)

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

        yield self.store.set_presence_state(target_user.localpart, state)

        # TODO(paul): Now this new state needs broadcasting to:
        #   every local user who is watching this one
        #   every remote HS on which at least one user is watching this one

    @defer.inlineCallbacks
    def send_invite(self, observer_user, observed_user):
        if not observer_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        yield self.store.add_presence_list_pending(
                observer_user.localpart, observed_user.to_string())

        if observed_user.is_mine:
            yield self.invite_presence(observed_user, observer_user)
        else:
            # TODO(paul): Hand this down to Federation
            pass

    @defer.inlineCallbacks
    def invite_presence(self, observed_user, observer_user):
        # TODO(paul): Eventually we'll ask the user's permission for this
        # before accepting. For now just accept any invite request
        yield self.store.allow_presence_inbound(
                observed_user.localpart, observer_user.to_string())

        if observer_user.is_mine:
            yield self.accept_presence(observed_user, observer_user)
        else:
            # TODO(paul): Hand this down to Federation
            pass

    @defer.inlineCallbacks
    def accept_presence(self, observed_user, observer_user):
        yield self.store.set_presence_list_accepted(
                observer_user.localpart, observed_user.to_string())

        # TODO(paul): Start exchanging messages
