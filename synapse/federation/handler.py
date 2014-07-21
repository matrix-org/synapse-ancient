# -*- coding: utf-8 -*-

from twisted.internet import defer

from synapse.api.events import SynapseEvent
from synapse.api.errors import AuthError


def _decode_event_id(event_id, local_server_name):
    parts = event_id.split("@", 1)
    if len(parts) < 2:
        return (event_id, local_server_name)
    else:
        return parts


def _event_from_pdu(pdu):
    kwargs = {}

    kwargs["event_id"] = "%s@%s" % (pdu.pdu_id, pdu.origin)
    kwargs["room_id"] = pdu.context
    kwargs["type"] = pdu.pdu_type
    kwargs["prev_events"] = ["%s@%s" % (p[0], p[1]) for p in pdu.prev_pdus]
    if hasattr(pdu, "prev_state_id") and hasattr(pdu, "prev_state_origin"):
        kwargs["prev_state"] = "%s@%s" % (
            pdu.prev_state_id, pdu.prev_state_origin
        )

    kwargs.update({
        k: v
        for k, v in pdu.get_dict().items()
        if k not in [
            "pdu_id",
            "origin",
            "context",
            "pdu_type",
            "prev_pdus",
            "prev_state_id",
            "prev_state_origin",
        ]
    })

    return SynapseEvent(**kwargs)


def _pdu_from_event(event, server_name):
    d = event.get_dict()

    d["pdu_id"], d["origin"] = _decode_event_id(event.event_id, server_name)
    d["context"] = event.room_id
    d["pdu_type"] = event.type

    if hasattr(event, "prev_events"):
        d["prev_pdus"] = [
            _decode_event_id(e.event_id, server_name)
            for e in event.prev_events
        ]

    if hasattr(event, "prev_state"):
        d["prev_state_id"], d["prev_state_origin"] = (
            _decode_event_id(event.prev_state, server_name)
        )

    kwargs = event.unrecognized_keys
    kwargs.update({
        k: v for k, v in d.items()
        if k not in ["event_id", "room_id", "type", "prev_events"]
    })

    return Pdu(**kwargs)


class FederationEventHandler(object):

    def __init__(self, hs):
        self.persistence = hs.get_persistence_service()
        self.replication_layer = hs.get_replication_layer()
        self.state_handler = hs.get_state_handler()
        self.auth_handler = gs.get_auth_handler()
        self.event_handler = (
            hs.get_event_handler_factory().federation_handler()
        )
        self.server_name = hostname

        self.replication_layer.set_handler(self)

    @defer.inlineCallbacks
    def handle_new_event(self, event):
        yield self.fill_out_prev_events(event)

        pdu = _pdu_from_event(event)

        pdu.destinations = yield self.persistence.get_servers_in_context(
            pdu.context
        )

        yield self.replication_layer.send_pdu(pdu)

    @defer.inlineCallbacks
    def fill_out_prev_events(self, event):
        if hasattr("prev_events", event):
            return

        results = yield self.service.get_latest_pdus_in_context(event.room_id)

        event.prev_events = [
            "%s@%s" % (p_id, origin) for p_id, origin, _ in results
        ]

        if results:
            event.depth = max([int(v) for _, _, v in results]) + 1
        else:
            event.depth = 0

    @defer.inlineCallbacks
    def backfill(self, room_id, limit):
        # TODO: Work out which destinations to ask for pagination
        # self.replication_layer.paginate(dest, room_id, limit)
        pass

    @defer.inlineCallbacks
    def on_receive_pdu(self, pdu):
        event = _event_from_pdu(pdu)

        try:
            yield self.auth_handler.check(event)

            def _on_new_state(self, new_state_event):
                return self._on_new_state(pdu, new_state_event)

            if event.is_state:
                yield self.state_handler.handle_new_state(
                    event,
                    _on_new_state
                )

                # TODO: Do we want to inform people about state_events that
                # result in a clobber?

                return
            else:
                yield self.event_handler.on_receive(event)

        except AuthError:
            # TODO: Implement something in federation that allows us to
            # respond to PDU.
            raise

        return

    @defer.inlineCallbacks
    def _on_new_state(self, pdu, new_state_event):
        # TODO: Do any persistence stuff here. Notifiy C2S about this new
        # state.

        yield self.persistence.update_current_state(
            pdu_id=pdu.pdu_id,
            origin=pdu.origin,
            context=pdu.context,
            pdu_type=pdu.pdu_type,
            state_key=pdu.state_key
        )

        yield self.event_handler.on_receive(new_state_event)
