# -*- coding: utf-8 -*-

from twisted.internet import defer

from transaction import TransactionCallbacks

from persistence.pdu import PduDbEntry, get_next_version
from protocol.units import Pdu

from persistence import queries

from collections import deque


class PduLayer(TransactionCallbacks):
    def send_pdu(self, pdu):
        pass


class PduCallbacks(object):
    def on_receive_pdu(self, pdu):
        pass


class SynapseDataLayer(PduLayer):

    def __init__(self, transaction_layer, callback):
        self.transaction_layer = transaction_layer
        self.callback = callback

        self.order = 0

        self.pdu_pending_queue = deque()

    def send_pdu(self, pdu):
        deferred = defer.Deferred()
        self.pdu_pending_queue.append((pdu, deferred))

        self._handle_queued_pdu()

        return deferred

    @defer.inlineCallbacks
    def on_received_pdus(self, pdu_list):
        dl = []
        for pdu in pdu_list:
            dl.append(self._handle_new_pdu(pdu))

        results = yield dl.deferredList(dl)

        ret = []
        for r in results:
            if r[0]:
                ret.append({})
            else:
                ret.append(r[1])

        defer.returnValue(ret)

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

    @defer.inlineCallbacks
    def _handle_new_pdu(self, pdu):
        # Have we seen this pdu before?
        existing = yield PduDbEntry.findBy(
                origin=pdu.origin, pdu_id=pdu.pdu_id)

        if existing:
            # We've already seen it, so we ignore it.
            defer.returnValue({})
            return

        ret = yield self.callback.on_receive_pdu(pdu)

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def _handle_queued_pdu(self):
        while self.pdu_pending_queue:
            pdu, deferred = self.pdu_pending_queue.popleft()

            next_ver = get_next_version(context)

            deferred.callback(None)
