# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError, AuthError
from synapse.api.constants import PresenceState

from ._base import BaseHandler

import logging


logger = logging.getLogger(__name__)


# TODO(paul): Maybe there's one of these I can steal from somewhere
def partition(l, func):
    """Partition the list by the result of func applied to each element."""
    ret = {}

    for x in l:
        key = func(x)
        if key not in ret:
            ret[key] = []
        ret[key].append(x)

    return ret


def partitionbool(l, func):
    def boolfunc(x):
        return bool(func(x))

    ret = partition(l, boolfunc)
    return ret.get(True, []), ret.get(False, [])


class PresenceHandler(BaseHandler):

    def __init__(self, hs):
        super(PresenceHandler, self).__init__(hs)

        self.homeserver = hs

        distributor = hs.get_distributor()
        distributor.observe("registered_user", self.registered_user)

        self.federation = hs.get_replication_layer()

        self.federation.register_edu_handler("sy.presence",
                self.incoming_presence)
        self.federation.register_edu_handler("sy.presence_invite",
                lambda origin, content: self.invite_presence(
                    observed_user=hs.parse_userid(content["observed_user"]),
                    observer_user=hs.parse_userid(content["observer_user"]),
                ))
        self.federation.register_edu_handler("sy.presence_accept",
                lambda origin, content: self.accept_presence(
                    observed_user=hs.parse_userid(content["observed_user"]),
                    observer_user=hs.parse_userid(content["observer_user"]),
                ))
        self.federation.register_edu_handler("sy.presence_deny",
                lambda origin, content: self.deny_presence(
                    observed_user=hs.parse_userid(content["observed_user"]),
                    observer_user=hs.parse_userid(content["observer_user"]),
                ))

        # IN-MEMORY store, mapping local userparts to sets of local users to
        # be informed of state changes.
        self._local_pushmap = {}
        # map local users to sets of remote /domain names/ who are interested
        # in them
        self._remote_sendmap = {}
        # map remote users to sets of local users who're interested in them
        self._remote_recvmap = {}

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

        logger.debug("Updating presence state of %s to %s",
                target_user.localpart, state["state"])

        oldstate = yield self.store.set_presence_state(target_user.localpart,
                state
        )

        now_online = state["state"] != PresenceState.OFFLINE
        was_online = oldstate != PresenceState.OFFLINE

        if now_online and not was_online:
            self.start_polling_presence(target_user)
        elif not now_online and was_online:
            self.stop_polling_presence(target_user)

        # TODO(paul): perform a presence push as part of start/stop poll so
        #   we don't have to do this all the time
        self.push_presence(target_user, state=state)

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
    def _should_accept_invite(self, observed_user, observer_user):
        if not observed_user.is_mine:
            defer.returnValue(False)

        row = yield self.store.has_presence_state(observed_user.localpart)
        if not row:
            defer.returnValue(False)

        # TODO(paul): Eventually we'll ask the user's permission for this
        # before accepting. For now just accept any invite request
        defer.returnValue(True)

    @defer.inlineCallbacks
    def invite_presence(self, observed_user, observer_user):
        accept = yield self._should_accept_invite(observed_user, observer_user)

        if accept:
            yield self.store.allow_presence_inbound(
                    observed_user.localpart, observer_user.to_string())

        if observer_user.is_mine:
            if accept:
                yield self.accept_presence(observed_user, observer_user)
            else:
                yield self.deny_presence(observed_user, observer_user)
        else:
            edu_type = "sy.presence_accept" if accept else "sy.presence_deny"

            yield self.federation.send_edu(
                    destination=observer_user.domain,
                    edu_type=edu_type,
                    content={
                        "observed_user": observed_user.to_string(),
                        "observer_user": observer_user.to_string(),
                    })

    @defer.inlineCallbacks
    def accept_presence(self, observed_user, observer_user):
        yield self.store.set_presence_list_accepted(
                observer_user.localpart, observed_user.to_string())

        self.start_polling_presence(observer_user, target_user=observed_user)

    @defer.inlineCallbacks
    def deny_presence(self, observed_user, observer_user):
        yield self.store.del_presence_list(
                observer_user.localpart, observed_user.to_string())

        # TODO(paul): Inform the user somehow?

    @defer.inlineCallbacks
    def drop(self, observed_user, observer_user):
        if not observer_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        yield self.store.del_presence_list(
                observer_user.localpart, observed_user.to_string())

        self.stop_polling_presence(observer_user, target_user=observed_user)

    @defer.inlineCallbacks
    def get_presence_list(self, observer_user, accepted=None):
        if not observer_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        presence = yield self.store.get_presence_list(observer_user.localpart,
                accepted=accepted)

        defer.returnValue([self.hs.parse_userid(x["observed_user_id"])
            for x in presence])

    @defer.inlineCallbacks
    def start_polling_presence(self, user, target_user=None, state=None):
        logger.debug("Start polling for presence from %s", user)

        if target_user:
            target_users = [target_user]
        else:
            presence = yield self.store.get_presence_list(
                    user.localpart, accepted=True)
            target_users = [self.hs.parse_userid(x["observed_user_id"])
                    for x in presence]

        if state is None:
            state = yield self.store.get_presence_state(user.localpart)

        localusers, remoteusers = partitionbool(target_users,
                lambda u: u.is_mine)

        deferreds = []
        for target_user in localusers:
            deferreds.append(self._start_polling_local(user, target_user))

        remoteusers_by_domain = partition(remoteusers, lambda u: u.domain)
        for domain in remoteusers_by_domain:
            remoteusers = remoteusers_by_domain[domain]

            deferreds.append(self._start_polling_remote(user, domain,
                remoteusers))

        yield defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def _start_polling_local(self, user, target_user):
        target_localpart = target_user.localpart

        # TODO(paul) permissions checks

        if target_localpart not in self._local_pushmap:
            self._local_pushmap[target_localpart] = set()

        self._local_pushmap[target_localpart].add(user)

        target_state = yield self.store.get_presence_state(target_localpart)

        yield self.push_update_to_clients(
                observer_user=user,
                observed_user=target_user,
                state=target_state,
        )

    def _start_polling_remote(self, user, domain, remoteusers):
        for u in remoteusers:
            if u not in self._remote_recvmap:
                self._remote_recvmap[u] = set()

            self._remote_recvmap[u].add(user)

        return self.federation.send_edu(
            destination=domain,
            edu_type="sy.presence",
            content={"poll": [u.to_string() for u in remoteusers]}
        )

    def stop_polling_presence(self, user, target_user=None):
        logger.debug("Stop polling for presence from %s", user)

        if not target_user or target_user.is_mine:
            self._stop_polling_local(user, target_user=target_user)

        deferreds = []

        if target_user:
            raise NotImplementedError("TODO: remove one user")

        remoteusers = [u for u in self._remote_recvmap if
                user in self._remote_recvmap[u]]
        remoteusers_by_domain = partition(remoteusers, lambda u: u.domain)

        for domain in remoteusers_by_domain:
            remoteusers = remoteusers_by_domain[domain]

            deferreds.append(
                    self._stop_polling_remote(user, domain, remoteusers))

        return defer.DeferredList(deferreds)

    def _stop_polling_local(self, user, target_user):
        for localpart in self._local_pushmap.keys():
            if target_user and localpart != target_user.localpart:
                continue

            if user in self._local_pushmap[localpart]:
                self._local_pushmap[localpart].remove(user)

            if not self._local_pushmap[localpart]:
                del self._local_pushmap[localpart]

    def _stop_polling_remote(self, user, domain, remoteusers):
        for u in remoteusers:
            self._remote_recvmap[u].remove(user)

            if not self._remote_recvmap[u]:
                del self._remote_recvmap[u]

        return self.federation.send_edu(
                destination=domain,
                edu_type="sy.presence",
                content={"unpoll": [u.to_string() for u in remoteusers]}
        )

    @defer.inlineCallbacks
    def push_presence(self, user, state=None):
        assert(user.is_mine)

        logger.debug("Pushing presence update from %s", user)

        localusers = self._local_pushmap.get(user.localpart, [])
        remotedomains = self._remote_sendmap.get(user.localpart, [])

        if not localusers and not remotedomains:
            defer.returnValue(None)

        if state is None:
            state = yield self.store.get_presence_state(user.localpart)

        deferreds = []
        for u in localusers:
            deferreds.append(self.push_update_to_clients(
                observer_user=u,
                observed_user=user,
                state=state
            ))

        for domain in remotedomains:
            deferreds.append(self._push_presence_remote(user, domain,
                state=state))

        yield defer.DeferredList(deferreds)

    @defer.inlineCallbacks
    def _push_presence_remote(self, user, destination, state=None):
        if state is None:
            state = yield self.store.get_presence_state(user.localpart)

        yield self.federation.send_edu(
            destination=destination,
            edu_type="sy.presence",
            content={
                "push": [
                    dict(user_id=user.to_string(), **state),
                ],
            }
        )

    @defer.inlineCallbacks
    def incoming_presence(self, origin, content):
        deferreds = []

        for push in content.get("push", []):
            user = self.hs.parse_userid(push["user_id"])

            logger.debug("Incoming presence update from %s", user)

            if user not in self._remote_recvmap:
                break

            observers = self._remote_recvmap[user]
            state = dict(push)
            del state["user_id"]

            for observer_user in observers:
                deferreds.append(self.push_update_to_clients(
                        observer_user=observer_user,
                        observed_user=user,
                        state=state
                ))

        for poll in content.get("poll", []):
            user = self.hs.parse_userid(poll)

            if not user.is_mine:
                continue

            # TODO(paul) permissions checks

            if not user in self._remote_sendmap:
                self._remote_sendmap[user] = set()

            self._remote_sendmap[user].add(origin)

            deferreds.append(self._push_presence_remote(user, origin))

        for unpoll in content.get("unpoll", []):
            user = self.hs.parse_userid(unpoll)

            if not user.is_mine:
                continue

            if user in self._remote_sendmap:
                self._remote_sendmap[user].remove(origin)

                if not self._remote_sendmap[user]:
                    del self._remote_sendmap[user]

        yield defer.DeferredList(deferreds)

    def push_update_to_clients(self, observer_user, observed_user, state):
        # TODO(paul)
        pass
