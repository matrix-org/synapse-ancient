# -*- coding: utf-8 -*-

from twisted.internet import defer, reactor

from Transaction import TransactionCallbacks

from db.pdy import PDU, CurrentStatePDUEntry, PDUDestination

import argparse
import time
import json
import random


class PduLayer(TransactionCallbacks):
    def send_pdu(self, pdu):
        """ Sends data to a group of remote home servers
        """
        pass

    def trigger_get_context_metadata(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass

    def get_delivery_status(self, pdu_id_list):
        """ For a given list of pdu_id's, return a dict of pdu_id -> dict of
            destination -> delivery status, as a deferred.

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

    def on_get_context_metadata(context):
        """ Get's called when we want to get all metadata pdus for a given
            context.
            Returns a list of dicts.
        """
        pass

    def on_received_pdu(origin, sent_ts, pdu_json):
        """ Get's called when we receive a pdu via a transaction.

            Returns a deferred which is called back when it has been
            successfully processed *and* persisted, or errbacks with either
            a) PduDecodeException, at which point we return a 400 on the
            entire transaction, or b) another exception at which point we
            respond with a 500 to the entire transaction.
        """
        pass

    def send_pdu(self, pdu):
        """ Sends data to a group of remote home servers
        """
        pass

    def trigger_get_context_metadata(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass

    def get_delivery_status(self, pdu_id_list):
        """ For a given list of pdu_id's, return a dict of pdu_id -> dict of
            destination -> delivery status, as a deferred.

        """
        pass