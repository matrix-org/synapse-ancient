# -*- coding: utf-8 -*-
""" This package includes all the federation specific logic.
"""

from .replication import ReplicationLayer, ReplicationHandler
from .transport import TransportLayer
from .units import Pdu


def initialize_http_federation(
        server_name, http_client, http_server, persistence_service):

    transport = TransportLayer(
        server_name,
        server=http_server,
        client=http_client
    )

    return ReplicationLayer(
        server_name,
        transport,
        persistence_service=persistence_service,
    )
