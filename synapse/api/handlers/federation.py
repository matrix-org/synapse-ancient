# -*- coding: utf-8 -*-
"""Contains handlers for federation events."""
from . import BaseHandler


class FederationHandler(BaseHandler):

    """Handles events that originated from federation."""

    def on_receive(self, event=None):
        pass
