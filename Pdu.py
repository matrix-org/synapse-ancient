# -*- coding: utf-8 -*-

from twisted.internet import defer

from Transaction import TransactionCallbacks, PduDecodeException

from db.pdu import PDU, CurrentStatePDUEntry, PDUDestination

import argparse
import time
import json
import random


class PduLayer(TransactionCallbacks):
    def send_pdu(self, pdu, destinations):
        """ Sends data to a group of remote home servers
        """
        pass

    def trigger_get_context_state(self, destination, context):
        """ Try and get the remote home server to give us all state about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass


class PduCallbacks(object):
    def on_receive_pdu(self, pdu):
        pass

    def get_pdu_content(self, pdu_id_list):
        pass


def get_origin(ucid):
    return ucid.split("@", 1)[1]


class SynapseDataLayer(PduLayer):

    def __init__(self, transaction_layer, callbacks):
        self.transaction_layer = transaction_layer
        self.callbacks = callbacks

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Get's called when we want to get a specific pdu
            Returns a dict representing the pdu
        """

        res = yield PDU.findBy(pdu_id=pdu_id, origin=pdu_origin)

        if len(res) != 1:
            defer.returnValue(None)
            return

        #content_res = yield self.callbacks.get_pdu_content(res[0].id)

        #if len(content_res) != 1:
        #    defer.returnValue(None)
        #    return

        d = res[0].to_dict()
        #d.content = content_res

        defer.returnValue(d)

    @defer.inlineCallbacks
    def on_get_context_state(self, context):
        """ Get's called when we want to get all metadata pdus for a given
            context.
            Returns a list of dicts.
        """
        # FIXME: Ask for content
        
        pdus = yield PDU.get_current_metadata_pdus(context)
        
        result = [p.to_dict() for p in pdus]
        
        defer.returnValue(result)
        
    @defer.inlineCallbacks
    def on_received_pdu(self, origin, sent_ts, pdu_json):
        """ Get's called when we receive a pdu via a transaction.

            Returns a deferred which is called back when it has been
            successfully processed *and* persisted, or errbacks with either
            a) PduDecodeException, at which point we return a 400 on the
            entire transaction, or b) another exception at which point we
            respond with a 500 to the entire transaction.
        """
        try:
            pdu = PDU.create_from_dict(pdu_json)
        except:
            raise PduDecodeException("Failed to parse pdu json")
        
        res = yield self.callbacks.on_receive_pdu(pdu)
        
        defer.returnValue(res)
        
        # We don't save the PDU until the layers above have persisted them
        yield pdu.save()

    def send_pdu(self, pdu, destinations):
        """ Sends data to a group of remote home servers
        """
        
        pdu_dict = pdu.to_dict()
        
        deferreds = []
        
        for dest in destinations:
            # First store where we're sending the pdu in the db.
            p = PDUDestination.create_from_pdu(pdu, dest).save()
            
            # Send it once it's done
            p.addCallback(
                      lambda x: 
                          self.transaction_layer.enqueue_pdu(dest, pdu_dict, 0)
                  )
            
            def update_status_and_save(x):
                p.delivered_ts = int(time.time() * 1000)
                return p.save()
            
            # Once we've finished sending it, update the delivered_status
            p.addCallback(update_status_and_save)
            
            deferreds.append(p)
            

        return defer.DeferredList(deferreds)

    def trigger_get_context_state(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        return self.transaction_layer.trigger_get_context_state(destination, context)

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        return self.transaction_layer.trigger_get_pdu(destination, pdu_origin, pdu_id)

        
        
        