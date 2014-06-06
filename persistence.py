# -*- coding: utf-8 -*-


class Persistence(object):

    def store_incoming_transaction(self, transaction):
        pass

    def store_outgoing_transaction(self, transaction):
        pass

    def get_incoming_transaction(self, origin, transaction_id):
        pass

    def get_outgoing_transaction(self, remote_server, transaction_id):
        pass

    def store_outgoing_pdu(self, pdu):
        pass

    def store_incoming_pdu(self, pdu):
        pass

    def get_incoming_pdu(self, origin, pdu_id):
        pass

    def get_outgoing_pdu(self, remote_server, pdu_id):
        pass

    def get_delivery_status(self, remote_server, pdu_id):
        pass

    def get_outgoing_pdus_from_version(self, version):
        pass

    def get_pdus_for_context_before_verison(self, version, context, limit):
        pass

    def update_forward_edges(self, pdu):
        pass

    def update_backward_edges(self, pdu):
        pass
