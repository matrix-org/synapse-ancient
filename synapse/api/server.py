# -*- coding: utf-8 -*-
"""This module serves as the top-level injection point for client-server
interactions."""

from synapse.api.auth import (Auth, AccessTokenModule,
                             JoinedRoomModule, MembershipChangeModule)
from synapse.api.event_store import EventStore
from synapse.api.events.factory import EventFactory
from synapse.api.handlers.factory import EventHandlerFactory
from synapse.rest.base import RestServletFactory
from synapse.federation import ReplicationHandler


class SynapseHomeServer(ReplicationHandler):

    def __init__(self, http_server, server_name, replication_layer):
        self.server_name = server_name
        self.http_server = http_server
        self.replication_layer = replication_layer
        self.replication_layer.set_handler(self)

        self.event_data_store = EventStore()

        # configure auth
        self.auth = Auth(
            AccessTokenModule(self.event_data_store),
            JoinedRoomModule(self.event_data_store),
            MembershipChangeModule(self.event_data_store)
            )

        # configure how events are made and handled
        self.event_factory = EventFactory()
        self.handler_factory = EventHandlerFactory(self.event_data_store,
                                                   self.event_factory,
                                                   self.auth)

        # configure how REST events are handled, and register paths
        self.rest_servlet_factory = RestServletFactory(self.handler_factory,
                                                       self.event_factory,
                                                       self.auth)
        self.rest_servlet_factory.register_servlets(self.http_server)

    def on_receive_pdu(self, pdu):
        pdu_type = pdu.pdu_type
        print "#%s (receive) *** %s" % (pdu.context, pdu_type)


