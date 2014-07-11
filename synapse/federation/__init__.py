# -*- coding: utf-8 -*-
""" This package includes all the federation specific logic.
"""

from .replication import ReplicationLayer, ReplicationHandler
from .transport import TransportLayer
from .persistence import PduActions, TransactionActions


def initialize_http_federation(server_name, http_client, http_server,
        pdu_actions=PduActions(), transaction_actions=TransactionActions()):
    transport = TransportLayer(
        server_name,
        server=http_server,
        client=http_client
    )
    return ReplicationLayer(server_name, transport,
            pdu_actions=pdu_actions, transaction_actions=transaction_actions)
