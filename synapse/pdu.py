# -*- coding: utf-8 -*-
""" The PDU layer is responsible for handling:
    - duplicate PDU ids
    - responding to requests for particular PDUs
    - responding to requests for current state PDUs for a given context
    - "versioning" outgoing PDUs by filling out `previous_pdus` property
    - Ensuring for incoming PDUs we have seen all the PDUs it references
"""

from twisted.internet import defer

from transaction import TransactionCallbacks
from persistence.pdu import (PduDbEntry, register_new_outgoing_pdu,
    register_remote_pdu, register_pdu_as_sent)
from protocol.units import Pdu

import logging


class PduCallbacks(object):
    """ A callback interface used by the PduLayer to inform layers above about
    new PDUs.
    """

    def on_receive_pdu(self, pdu):
        """ We received a PDU. Someone should handle that.

        Args:
            pdu (synapse.protocol.units.Pdu): The PDU we received.

        Returns:
            Deferred: Results in a dict that used as the response to the PDU.
        """
        pass

    def on_unseen_pdu(self, originating_server, pdu_id, origin):
        """ We have seen a reference to a PDU we don't have. Usually someone
        specifically asks some remote home server for it.

        Args:
            originating_server (str): The home server that referenced the
                unrecognized PDU.

            pdu_id (str): The pdu id of the unseen PDU

            origin (str): The origin of the unseen PDU.

        Returns:
            Deferred
        """
        pass


class PduLayer(TransactionCallbacks):
    """
    Attributes:
        transaction_layer (synapse.transaction.TransactionLayer): The
            transaction layer we use to to send PDUs.

        callback (synapse.pdu.PduCallbacks): The currently registered callback.
    """

    def __init__(self, transaction_layer):
        """
        Args:
            transaction_layer (synapse.transaction.TransactionLayer): The
                transaction layer we use to to send PDUs.
        """

        self.transaction_layer = transaction_layer

        self.transaction_layer.set_callback(self)

        self.callback = None

        self._order = 0

    def set_callback(self, callback):
        self.callback = callback

    @defer.inlineCallbacks
    def send_pdu(self, pdu):
        """ Sends a PDU. This takes care of handling the versions.

        Args:
            pdu (synapse.protocol.units.Pdu): The PDU to send

        Returns:
            Deferred: That succeeds when we have successfully sent the PDU

        """
        # We need to define the ordering *before* we yield to set the new
        # version.
        order = self._order
        self._order += 1

        # Save *before* trying to send
        yield pdu.persist()

        # This fills out the previous_pdus property
        yield register_new_outgoing_pdu(pdu)

        yield self.transaction_layer.enqueue_pdu(pdu, order)

        # Deletes the appropriate entries in the extremeties table
        yield register_pdu_as_sent(pdu)

    @defer.inlineCallbacks
    def on_received_pdus(self, pdu_list):
        """
        Overrides:
            TransactionCallbacks
        """
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
                logging.exception(r[1])
                ret.append({"error": str(r[1])})

        logging.debug("Returning: %s", str(ret))

        defer.returnValue((200, ret))

    def on_context_state_request(self, context):
        """
        Overrides:
            TransactionCallbacks
        """

        return Pdu.get_state(context)

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """
        Overrides:
            TransactionCallbacks
        """

        results = yield PduDbEntry.findBy(origin=pdu_origin, pdu_id=pdu_id)

        #pdus = [Pdu.from_db_entry(r) for r in results]
        pdus = yield Pdu.from_db_entries(results)

        if not pdus:
            defer.returnValue(None)
            return

        yield defer.DeferredList([p.get_previous_pdus_from_db() for p in pdus])

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def _handle_new_pdu(self, pdu):
        logging.debug("_handle_new_pdu %s from %s",
                        str(pdu.pdu_id), pdu.origin)

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

        # Save *after* we have processed
        yield pdu.persist()

        defer.returnValue(ret)
