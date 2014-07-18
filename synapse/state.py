# -*- coding: utf-8 -*-

from twisted.internet import defer

import hashlib


class StateHandler(object):
    """ StateHandler is repsonsible for doing state conflict resolution.
    """

    def __init__(self, persistence_service, replication_layer):
        self._persistence = persistence_service
        self._replication = replication_layer

        self._update_deferreds = {}

    @defer.inlineCallbacks
    def handle_new_state_event(self, new_event, new_state_callback=None):
        new_deferred = defer.Deferred()
        yield self._lock_on_key(
            new_deferred,
            new_event.room_id, new_event.event_type, new_event.state_key
        )

        current_state_pdu = yield self._persistence.get_current_state(
            new_event.room_id, new_event.type, new_event.state_key
        )

        if current_state_pdu:
            # TODO: Check power levels.

            new_event.prev_state = "%s@%s" % (
                current_state_pdu.pdu_id, current_state_pdu.origin
            )

        yield defer.maybeDeferred(new_state_callback(new_event))

        pdu_id, origin = new_event.event_id.split("@", 1)

        yield self._persistence.update_current_state(
            pdu_id=pdu_id,
            origin=origin,
            context=new_event.room_id,
            pdu_type=new_event.event_type,
            state_key=new_event.state_key
        )

    @defer.inlineCallbacks
    def handle_new_state_pdu(self, new_pdu, new_state_callback=None):
        """ Apply conflict resolution to `new_pdu`.

        This should be called on every new state pdu, regardless of whether or
        not there is a conflict.

        This function is safe against the race of it getting called with two
        `PDU`s trying to update the same state.
        """
        new_deferred = defer.Deferred()
        yield self._lock_on_key(
            new_deferred,
            new_pdu.context, new_pdu.pdu_type, new_pdu.state_key
        )

        is_new = yield self._handle_new_state_pdu(new_pdu)

        if is_new and new_state_callback:
            yield defer.maybeDeferred(new_state_callback(new_pdu))

            yield self._persistence.update_current_state(
                pdu_id=new_pdu.pdu_id,
                origin=new_pdu.origin,
                context=new_pdu.context,
                pdu_type=new_pdu.pdu_type,
                state_key=new_pdu.state_key
            )

        new_deferred.callback(None)

        defer.returnValue(is_new)

    @defer.inlineCallbacks
    def _lock_on_key(self, new_deferred, context, event_type, state_key):
        """ Make sure that we only ever handle one state event/pdu at a time
        for a given (context, event_type, state_key) tuple.

        This blocks until it's safe for the caller to do stuff. When the
        caller has finished, it should resolve the `new_deferred`
        """
        key = (context, event_type, state_key)

        old_deferred = self._update_deferreds.get(key)
        self._update_deferreds[key] = new_deferred

        if old_deferred:
            yield old_deferred

    @defer.inlineCallbacks
    def _handle_new_state_pdu(self, new_pdu):
        tree = yield self._persistence.get_unresolved_state_tree(new_pdu)
        new_branch, current_branch = tree

        # We currently don't persist here now. But if you were you would use:
        # yield self._persistence.update_current_state(
        #     pdu_id=new_pdu.pdu_id,
        #     origin=new_pdu.origin,
        #     context=new_pdu.context,
        #     pdu_type=new_pdu.pdu_type,
        #     state_key=new_pdu.state_key
        # )

        if not current_branch:
            # There is no current state
            defer.returnValue(True)
            return

        if new_branch[-1] == current_branch[-1]:
            # We have all the PDUs we need, so we can just do the conflict
            # resolution.

            if len(current_branch) == 1:
                # This is a direct clobber so we can just...
                defer.returnValue(True)

            conflict_res = [
                self._do_power_level_conflict_res,
                self._do_chain_length_conflict_res,
                self._do_hash_conflict_res,
            ]

            for algo in conflict_res:
                new_res, curr_res = algo(new_branch, current_branch)

                if new_res < curr_res:
                    defer.returnValue(False)
                elif new_res > curr_res:
                    defer.returnValue(True)

            raise Exception("Conflict resolution failed.")

        else:
            # We need to ask for PDUs.
            missing_prev = max(
                new_branch[-1], current_branch[-1],
                key=lambda x: x.depth
            )

            yield self._replication.get_pdu(
                destination=missing_prev.origin,
                pdu_origin=missing_prev.prev_state_origin,
                pdu_id=missing_prev.prev_state_id,
                outlier=True
            )

            updated_current = yield self._handle_new_state_pdu(new_pdu)
            defer.returnValue(updated_current)

    def _do_power_level_conflict_res(self, new_branch, current_branch):
        max_power_new = max(
            new_branch[:-1],
            key=lambda t: t.power_level
        ).power_level

        max_power_current = max(
            current_branch[:-1],
            key=lambda t: t.power_level
        ).power_level

        return (max_power_new, max_power_current)

    def _do_chain_length_conflict_res(self, new_branch, current_branch):
        return (len(new_branch), len(current_branch))

    def _do_hash_conflict_res(self, new_branch, current_branch):
        new_str = "".join([p.pdu_id + p.origin for p in new_branch])
        c_str = "".join([p.pdu_id + p.origin for p in current_branch])

        return (
            hashlib.sha1(new_str).hexdigest(),
            hashlib.sha1(c_str).hexdigest()
        )
