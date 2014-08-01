# -*- coding: utf-8 -*-
from twisted.internet import defer

from synapse.api.errors import SynapseError, AuthError
from synapse.api.constants import PresenceState
from synapse.api.streams import StreamData

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

        # map any user to a UserPresenceCache
        self._user_cachemap = {}
        self._user_cachemap_latest_serial = 0

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
            # TODO(paul): Have remote server send us permissions set
            if target_user in self._user_cachemap:
                defer.returnValue(
                        self._user_cachemap[target_user].get_state())
            else:
                defer.returnValue({"state": 0, "status_msg": ""})

    @defer.inlineCallbacks
    def set_state(self, target_user, auth_user, state):
        if not target_user.is_mine:
            raise SynapseError(400, "User is not hosted on this Home Server")

        if target_user != auth_user:
            raise AuthError(400, "Cannot set another user's displayname")

        # TODO(paul): Sanity-check 'state'
        if "status_msg" not in state:
            state["status_msg"] = None

        for k in state.keys():
            if k not in ("state", "status_msg"):
                raise SynapseError(400,
                        "Unexpected presence state key '%s'" % (k))

        logger.debug("Updating presence state of %s to %s",
                target_user.localpart, state["state"])

        oldstate = yield self.store.set_presence_state(target_user.localpart,
                state
        )

        now_online = state["state"] != PresenceState.OFFLINE
        was_online = oldstate["state"] != PresenceState.OFFLINE

        if target_user not in self._user_cachemap:
            self._user_cachemap[target_user] = UserPresenceCache()

        statuscache = self._user_cachemap[target_user]

        self._user_cachemap_latest_serial += 1
        statuscache.update(state, serial=self._user_cachemap_latest_serial)

        if now_online and not was_online:
            self.start_polling_presence(target_user, state=state)
        elif not now_online and was_online:
            self.stop_polling_presence(target_user)

        # TODO(paul): perform a presence push as part of start/stop poll so
        #   we don't have to do this all the time
        self.push_presence(target_user, statuscache=statuscache)

        if not now_online:
            del self._user_cachemap[target_user]

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

        for p in presence:
            observed_user = self.hs.parse_userid(p.pop("observed_user_id"))
            p["observed_user"] = observed_user

            if observed_user in self._user_cachemap:
                p.update(self._user_cachemap[observed_user].get_state())

        defer.returnValue(presence)

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

        if target_user not in self._user_cachemap:
            self._user_cachemap[target_user] = UserPresenceCache()

        statuscache = self._user_cachemap[target_user]

        self._user_cachemap_latest_serial += 1
        statuscache.update(target_state,
                serial=self._user_cachemap_latest_serial)

        self.push_update_to_clients(
                observer_user=user,
                observed_user=target_user,
                statuscache=statuscache,
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
    def push_presence(self, user, statuscache):
        assert(user.is_mine)

        logger.debug("Pushing presence update from %s", user)

        localusers = self._local_pushmap.get(user.localpart, [])
        remotedomains = self._remote_sendmap.get(user.localpart, [])

        if not localusers and not remotedomains:
            defer.returnValue(None)

        for u in localusers:
            self.push_update_to_clients(
                observer_user=u,
                observed_user=user,
                statuscache=statuscache,
            )

        deferreds = []
        for domain in remotedomains:
            deferreds.append(self._push_presence_remote(user, domain,
                state=statuscache.get_state()))

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

            if user not in self._user_cachemap:
                self._user_cachemap[user] = UserPresenceCache()

            statuscache = self._user_cachemap[user]

            self._user_cachemap_latest_serial += 1
            statuscache.update(state, serial=self._user_cachemap_latest_serial)

            for observer_user in observers:
                self.push_update_to_clients(
                        observer_user=observer_user,
                        observed_user=user,
                        statuscache=statuscache,
                )

            if state["state"] == PresenceState.OFFLINE:
                del self._user_cachemap[user]

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

    def push_update_to_clients(self, observer_user, observed_user,
            statuscache):
        self.notifier.on_new_user_event(observer_user.to_string(),
                event_data=statuscache.make_event(user=observed_user),
                stream_type=PresenceStreamData,
                store_id=statuscache.serial)


class PresenceStreamData(StreamData):
    def __init__(self, hs):
        super(PresenceStreamData, self).__init__(hs)
        self.presence = hs.get_handlers().presence_handler

    def get_rows(self, user_id, from_key, to_key, limit):
        cachemap = self.presence._user_cachemap

        # TODO(paul): limit, and filter by visibility
        updates = [(k, cachemap[k]) for k in cachemap
                if from_key < cachemap[k].serial <= to_key]

        if updates:
            latest_serial = max([x[1].serial for x in updates])
            data = [x[1].make_event(user=x[0]) for x in updates]
            return ((data, latest_serial))
        else:
            return (([], 0))  # TODO(paul): is 0 correct?

    def max_token(self):
        return self.presence._user_cachemap_latest_serial

PresenceStreamData.EVENT_TYPE = PresenceStreamData


class UserPresenceCache(object):
    """Store an observed user's state and status message.

    Includes the update timestamp.
    """
    def __init__(self):
        self.state = None
        self.status_msg = None
        self.serial = None

    def update(self, state, serial):
        self.state = state["state"]
        self.serial = serial

        if "status_msg" in state:
            self.status_msg = state["status_msg"]
        else:
            self.status_msg = None

    def get_state(self):
        ret = {"state": self.state}

        if self.status_msg is not None:
            ret["status_msg"] = self.status_msg

        return ret

    def make_event(self, user):
        content = self.get_state()
        content["user_id"] = user.to_string()

        return {"type": "sy.presence", "content": content}
