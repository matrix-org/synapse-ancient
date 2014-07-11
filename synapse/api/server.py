# -*- coding: utf-8 -*-
"""This module serves as the top-level injection point for client-server
interactions."""

from synapse.api.auth import Auth, RegisteredUserModule
from synapse.api.events.base import EventFactory
from synapse.api.event_store import EventStore
from synapse.federation import ReplicationHandler


class SynapseHomeServer(ReplicationHandler):

    def __init__(self, http_server, server_name, replication_layer):
        self.server_name = server_name
        self.http_server = http_server
        self.replication_layer = replication_layer
        self.replication_layer.set_handler(self)

        self.event_data_store = EventStore()

        # configure auth
        Auth.mod_registered_user = RegisteredUserModule(self.event_data_store)

        self.event_factory = EventFactory()
        self.event_factory.register_events(self.http_server,
                                           self.event_data_store)

    def on_receive_pdu(self, pdu):
        pdu_type = pdu.pdu_type
        print "#%s (receive) *** %s" % (pdu.context, pdu_type)


