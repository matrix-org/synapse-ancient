# -*- coding: utf-8 -*-

from twisted.internet import defer


class StateHandler(object):

    def __init__(self, persistence_service, replication_layer):
        self._persistence = persistence_service
        self._replication = replication_layer

        self._update_deferreds = {}

    @defer.inlineCallbacks
    def handle_new_state(self, new_pdu):
        key = (new_pdu.context, new_pdu.pdu_type, new_pdu.state_key)

        old_deferred = self._update_deferreds.get(key)
        new_deferred = defer.Deferred()
        self._update_deferreds[key] = new_deferred

        if old_deferred:
            yield old_deferred

        ret = yield self._handle_new_state(new_pdu)
        new_deferred.callback(None)

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def _handle_new_state(self, new_pdu):
        tree = yield self._persistence.get_unresolved_state_tree(new_pdu)
        new_branch, current_branch = tree

        if not current_branch:
            # There is no current state
            yield self._persistence.update_current_state(
                    pdu_id=new_pdu.pdu_id,
                    origin=new_pdu.origin,
                    context=new_pdu.context,
                    pdu_type=new_pdu.pdu_type,
                    state_key=new_pdu.state_key
                )

        if new_branch[-1] == current_branch[-1]:
            # We have all the PDUs we need, so we can just do the conflict
            # resolution.

            update_current = False

            max_power_new = max(
                new_branch,
                key=lambda t: t.power_level
            ).power_level

            max_power_current = max(
                current_branch,
                key=lambda t: t.power_level
            ).power_level

            if max_power_new > max_power_current:
                # Do the update of current_state
                update_current = True
            elif max_power_new == max_power_current:
                # We need to apply more conflict resolution.
                update_current = len(new_branch) > len(current_branch)
            else:
                # The new state doesn't clobber.
                pass

            if update_current:
                yield self._persistence.update_current_state(
                    pdu_id=new_pdu.pdu_id,
                    origin=new_pdu.origin,
                    context=new_pdu.context,
                    pdu_type=new_pdu.pdu_type,
                    state_key=new_pdu.state_key
                )

            defer.returnValue(update_current)

        else:
            # We need to ask for PDUs.
            missing_prev = max(
                new_branch[-1], current_branch[-1],
                key=lambda x: x.depth
            )

            yield self._replication.get_pdu(
                missing_prev.origin,
                missing_prev.prev_state_id,
                missing_prev.prev_state_origin
            )

            updated_current = yield self.handle_new_state(new_pdu)
            defer.returnValue(updated_current)