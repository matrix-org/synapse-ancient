# -*- coding: utf-8 -*-

from twisted.internet import defer

from transaction import TransactionCallbacks

from persistence.pdu import PduDbEntry
from protocol.units import Pdu

from persistence import queries


class PduLayer(TransactionCallbacks):
        pass


class PduCallbacks(object):
    def on_receive_pdu(self, pdu):
        pass


def get_origin(ucid):
    return ucid.split("@", 1)[1]


class SynapseDataLayer(PduLayer):

    def __init__(self, transaction_layer, callbacks):
        self.transaction_layer = transaction_layer
        self.callbacks = callbacks

    def on_received_pdus(self, pdu_list):
        pass

    def on_context_state_request(self, context):
        return queries.get_state_pdus_for_context(context)

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        results = yield PduDbEntry.findBy(origin=pdu_origin, pdu_id=pdu_id)

        pdus = [Pdu.from_db_entry(r) for r in results]

        if not pdus:
            defer.returnValue(None)
            return

        yield defer.DeferredList([p.get_previous_pdus_from_db() for p in pdus])

        defer.returnValue(pdus)