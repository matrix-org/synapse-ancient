# -*- coding: utf-8 -*-
""" This package includes all the federation specific logic.
"""

from .replication import ReplicationLayer
from .transport import TransportLayer


def initialize_http_replication(homeserver):
    transport = TransportLayer(
        homeserver.hostname,
        server=homeserver.get_http_server(),
        client=homeserver.get_http_client()
    )

    return ReplicationLayer(homeserver, transport)
