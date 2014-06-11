# -*- coding: utf-8 -*-

from twisted.internet import defer

from transaction import TransactionCallbacks
from persistence.pdu import (PduDbEntry, register_new_outgoing_pdu,
    register_remote_pdu, register_pdu_as_sent)
from protocol.units import Pdu

import logging


class PduLayer(TransactionCallbacks):
    """ Responsible for handling duplicate pdu_ids as well as versioning.
    """
    def send_pdu(self, pdu):
        """ Sends a PDU. This takes care of handling the versions
        """
        pass


class PduCallbacks(object):
    def on_receive_pdu(self, pdu):
        """ We received a PDU. Someone should handle that.
        """
        pass

    def on_unseen_pdu(self, originating_server, pdu_id, origin):
        pass


class SynapsePduLayer(PduLayer):

    def __init__(self, transaction_layer):
        self.transaction_layer = transaction_layer

        self.transaction_layer.set_callback(self)

        self.callback = None

        self.order = 0

    def set_callback(self, callback):
        self.callback = callback

    @defer.inlineCallbacks
    def send_pdu(self, pdu):
        # We need to define the ordering *before* we yield to set the new
        # version.
        order = self.order
        self.order += 1

        # This fills out the previous_pdus property
        yield register_new_outgoing_pdu(pdu)

        yield self.transaction_layer.enqueue_pdu(pdu, order)

        # Deletes the appropriate entries in the extremeties table
        yield register_pdu_as_sent(pdu)

    @defer.inlineCallbacks
    def on_received_pdus(self, pdu_list):
        # We got a bunch of pdus. Handle them "concurrently" (i.e., don't
        # indvidually yield), so pass them off to the _handle_new_pdu and then
        # yield on the deferred list
        dl = []
        for pdu in pdu_list:
            dl.append(self._handle_new_pdu(pdu))

        results = yield defer.DeferredList(dl)

        # Generate an appropriate return value from the DeferredList results
        ret = []
        for r in results:
            if r[0]:
                ret.append({})
            else:
                ret.append(r[1])

        logging.debug("Returning: %s", str(ret))

        defer.returnValue((200, ret))

    def on_context_state_request(self, context):
        return Pdu.get_state(context)

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
        logging.debug("_handle_new_pdu")

        # Have we seen this pdu before?
        existing = yield PduDbEntry.findBy(
                origin=pdu.origin, pdu_id=pdu.pdu_id)

        if existing:
            # We've already seen it, so we ignore it.
            defer.returnValue({})
            return

        # Now we check to see if we have seen the pdus it references.
        for pdu_id, origin in pdu.previous_pdus:
            exists = yield PduDbEntry.findBy(
                origin=origin, pdu_id=pdu_id)
            if not exists:
                # Oh no! We better request it.
                self.callback.on_unseen_pdu(
                        pdu.origin,
                        pdu_id=pdu_id,
                        origin=origin
                    )

        # Update the edges + extremeties table
        yield register_remote_pdu(pdu)

        # Inform callback
        ret = yield self.callback.on_receive_pdu(pdu)

        defer.returnValue(ret)
