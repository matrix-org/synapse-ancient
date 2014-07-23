# -*- coding: utf-8 -*-


from synapse.api.events import SynapseEvent
from .units import Pdu

import copy
import time


def decode_event_id(event_id, server_name):
    parts = event_id.split("@")
    if len(parts) < 2:
        return (event_id, server_name)
    else:
        return (parts[0], "".join(parts[1:]))


def encode_event_id(pdu_id, origin):
    return "%s@%s" % (pdu_id, origin)


class PduCodec(object):

    def __init__(self, hs):
        self.server_name = hs.hostname
        self.event_factory = hs.get_event_factory()

    def event_from_pdu(self, pdu):
        kwargs = {}

        kwargs["event_id"] = encode_event_id(pdu.pdu_id, pdu.origin)
        kwargs["room_id"] = pdu.context
        kwargs["etype"] = pdu.pdu_type
        kwargs["prev_events"] = [
            encode_event_id(p[0], p[1]) for p in pdu.prev_pdus
        ]

        if hasattr(pdu, "prev_state_id") and hasattr(pdu, "prev_state_origin"):
            kwargs["prev_state"] = encode_event_id(
                pdu.prev_state_id, pdu.prev_state_origin
            )

        kwargs.update({
            k: v
            for k, v in pdu.get_full_dict().items()
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

        return self.event_factory.create_event(**kwargs)

    def pdu_from_event(self, event):
        d = event.get_full_dict()

        d["pdu_id"], d["origin"] = decode_event_id(
            event.event_id, self.server_name
        )
        d["context"] = event.room_id
        d["pdu_type"] = event.type

        if hasattr(event, "prev_events"):
            d["prev_pdus"] = [
                decode_event_id(e, self.server_name)
                for e in event.prev_events
            ]

        if hasattr(event, "prev_state"):
            d["prev_state_id"], d["prev_state_origin"] = (
                decode_event_id(event.prev_state, self.server_name)
            )

        kwargs = copy.deepcopy(event.unrecognized_keys)
        kwargs.update({
            k: v for k, v in d.items()
            if k not in ["event_id", "room_id", "type", "prev_events"]
        })

        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)

        return Pdu(**kwargs)
