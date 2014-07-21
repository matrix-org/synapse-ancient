# -*- coding: utf-8 -*-
"""This module serves as the top-level injection point for client-server
interactions."""

from synapse.federation import ReplicationHandler


class SynapseHomeServer(ReplicationHandler):
    def __init__(self, hs):
        self.server_name = hs.hostname

        hs.get_federation().set_handler(self)

        hs.get_rest_servlet_factory().register_servlets(hs.get_http_server())

    def on_receive_pdu(self, pdu):
        pdu_type = pdu.pdu_type
        print "#%s (receive) *** %s" % (pdu.context, pdu_type)


