# -*- coding: utf-8 -*-
"""Contains handlers for federation events."""

from ._base import BaseHandler

from synapse.api.events.room import InviteJoinEvent, RoomMemberEvent
from synapse.api.constants import Membership
from synapse.types import UserID
from synapse.util.logutils import log_function

from twisted.internet import defer

import logging


logger = logging.getLogger(__name__)


class FederationHandler(BaseHandler):

    """Handles events that originated from federation."""

    @log_function
    @defer.inlineCallbacks
    def on_receive(self, event, is_new_state):
        if hasattr(event, "state_key") and not is_new_state:
            logger.debug("Ignoring old state.")
            return

        target_is_mine = False
        target_user = None
        if hasattr(event, "target_user_id"):
            target_user = UserID.from_string(event.target_user_id, self.hs)
            target_is_mine = target_user.is_mine

        if event.type == InviteJoinEvent.TYPE:
            if not target_is_mine:
                logger.debug("Ignoring invite/join event %s", target_user)
                logger.debug("Event: %s", event)
                return

            # If we receive an invite/join event then we need to join the
            # sender to the given room.
            # TODO: We should probably auth this or some such
            content = {"membership": Membership.JOIN}
            new_event = self.event_factory.create_event(
                etype=RoomMemberEvent.TYPE,
                target_user_id=event.user_id,
                room_id=event.room_id,
                user_id=event.user_id,
                membership=Membership.JOIN,
                content=content
            )

            yield self.hs.get_handlers().room_member_handler.change_membership(
                new_event,
                True
            )

        else:
            with (yield self.room_lock.lock(event.room_id)):
                store_id = yield self.store.persist_event(event)

            yield self.notifier.on_new_event(event, store_id)
