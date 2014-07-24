# -*- coding: utf-8 -*-
"""Contains handlers for federation events."""

from ._base import BaseHandler
from .room import MessageEvent

from synapse.util.logutils import log_function

from twisted.internet import defer

import json
import logging


logger = logging.getLogger(__name__)


class FederationHandler(BaseHandler):

    """Handles events that originated from federation."""

    @log_function
    @defer.inlineCallbacks
    def on_receive(self, event):
        store_id = yield self.store.persist_event(event)
        yield self.notifier.on_new_event(event, store_id)
