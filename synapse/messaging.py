# -*- coding: utf-8 -*-

from pdu import PduCallbacks
from protocol.units import Pdu

import logging


logger = logging.getLogger("synapse.messaging")


class MessagingCallbacks(object):
    """ A callback interface used to inform layers above about
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


class MessagingLayer(PduCallbacks):
    """ This is (for now) simply providing a nice interface for people who want
    to use the server to server stuff.

    Args:
        server_name (str): The local host.
        transport_layer (synapse.transport.TransportLayer): The transport layer
            to use to send requests.
        pdu_layer (synapse.pdu.PduLayer): The pdu layer we use to send PDUs.
        callack (MessagingCallbacks, optional): The callback to use to inform
            the application about new PDUs. Defaults to None.

    Attributes:
        server_name (str): The local host.
        transport_layer (synapse.transport.TransportLayer): The transport layer
            to use to send requests.
        pdu_layer (synapse.pdu.PduLayer): The pdu layer we use to send PDUs.
        callack (MessagingCallbacks, optional): The callback to use. Defaults
            to None.

    """
    def __init__(self, server_name, transport_layer, pdu_layer, callback=None):
        self.transport_layer = transport_layer
        self.pdu_layer = pdu_layer
        self.server_name = server_name
        self.callback = callback

        self.pdu_layer.set_callback(self)

    def set_callback(self, callback):
        """ Change the current callback

        Args:
            callack (MessagingCallbacks): The callback to use to inform
            the application about new PDUs.
        """
        self.callback = callback

    def on_receive_pdu(self, pdu):
        """
        Overrides:
            synapse.pdu.PduCallbacks
        """
        return self.callback.on_receive_pdu(pdu)

    def on_unseen_pdu(self, originating_server, pdu_id, origin):
        """
        Overrides:
            synapse.pdu.PduCallbacks
        """
        return self.transport_layer.trigger_get_pdu(
            originating_server, pdu_id, origin)

    def send_pdu(self, pdu):
        """ Send a PDU.
        Args:
            pdu (synapse.protocol.units.Pdu): The pdu to send.

        Returns:
            Deferred: Succeeds when we have finished attempting to deliver the
                PDU.
        """
        return self.pdu_layer.send_pdu(pdu)

    def get_context_state(self, destination, context):
        """ Triggers a request to get the current state for a context from
        the given remote home server.

        Args:
            destination (str): The remote home server to get the state from.
            context (str): The context to get the state for.

        Returns:
            Deferred: Succeeds when we have finished processing the response.

            ``Note``: This does not result in the context state.
        """
        logger.debug("get_context_state")
        return self.transport_layer.trigger_get_context_state(destination,
            context)

    def send_state(self, destinations, context, pdu_type, state_key, content):
        """ Convenience method for creating and sending a state PDU.

        Args:
            destinations (list): A list of remote home servers to send the PDU
                to.
            context (str): The context of the new PDU.
            pdu_type (str): The type of the PDU.
            state_key (str): The state key
            content (dict): The content to send.

        Returns:
            Deferred: Succeeds when we have finished attempting to deliver the
                PDU.
        """
        pdu = Pdu.create_new(
                    context=context,
                    origin=self.server_name,
                    pdu_type=pdu_type,
                    destinations=destinations,
                    is_state=True,
                    state_key=state_key,
                    content=content
                )

        return self.send_pdu(pdu)

    def send(self, destinations, context, pdu_type, content):
        """ Convenience method for creating and sending a non-state PDU.

        Args:
            destinations (list): A list of remote home servers to send the PDU
                to.
            context (str): The context of the new PDU.
            pdu_type (str): The type of the PDU.
            content (dict): The content to send.

        Returns:
            Deferred: Succeeds when we have finished attempting to deliver the
                PDU.
        """
        pdu = Pdu.create_new(
                context=context,
                origin=self.server_name,
                pdu_type=pdu_type,
                destinations=destinations,
                content=content
            )

        return self.send_pdu(pdu)