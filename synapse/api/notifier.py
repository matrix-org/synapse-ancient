# -*- coding: utf-8 -*-
from synapse.api.constants import Membership
from synapse.api.events.room import RoomMemberEvent

from twisted.internet import defer
from twisted.internet import reactor

import logging

logger = logging.getLogger(__name__)


class Notifier(object):

    def __init__(self, hs):
        self.store = hs.get_event_data_store()
        self.hs = hs
        self.stored_event_listeners = {}

    @defer.inlineCallbacks
    def on_new_event(self, event, store_id):
        """Called when there is a new event which may potentially be sent down
        a listening user's event stream.

        Args:
            event (SynapseEvent): The new event
            store_id (int): The ID of this event after it was stored with the
            data store.
        '"""
        # prod everyone who is online in the room
        member_list = yield self.store.get_room_members(room_id=event.room_id,
                                                        membership="join")
        if member_list:
            for member in member_list:
                if member.user_id in self.stored_event_listeners:
                    logger.debug(("Notifying %s of a new event." %
                                 member.user_id))
                    # work out the new end token
                    stream_handler = (self.hs.get_event_handler_factory().
                                        event_stream_handler())
                    end = stream_handler.get_event_stream_token(
                        event,
                        store_id,
                        self.stored_event_listeners[member.user_id]["start"]
                        )
                    self.stored_event_listeners[member.user_id]["end"] = end

                    # add the event to the chunk
                    chunk = self.stored_event_listeners[member.user_id]["chunk"]
                    chunk.append(event.get_dict())

                    # callback the defer
                    d = self.stored_event_listeners[member.user_id].pop("defer")
                    d.callback(self.stored_event_listeners[member.user_id])

        # TODO invites MUST prod the person being invited, as well as people in
        # the room
        # if (event.type == RoomMemberEvent.TYPE and
        #         event.membership == Membership.INVITE):
        #     print "invite: prod %s" % event.target_user_id

    def store_events_for(self, user_id=None, from_tok=None):
        """Store all incoming events for this user. This should be paired with
        get_events_for to return chunked data.

        Args:
            user_id (str): The user to monitor incoming events for.
            from_tok (str): The token to monitor incoming events from.
        """
        self.stored_event_listeners[user_id] = {
                "start": from_tok,
                "chunk": [],
                "end": from_tok
            }

    def purge_events_for(self, user_id=None):
        """Purges any stored events for this user.

        Args:
            user_id (str): The user to purge stored events for.
        """
        try:
            self.stored_event_listeners.pop(user_id)
        except KeyError:
            pass

    def get_events_for(self, user_id=None, timeout=0):
        """Retrieve stored events for this user, waiting if necessary.

        It is advisable to wrap this call in a maybeDeferred.

        Args:
            user_id (str): The user to get events for.
            timeout (int): The time in seconds to wait before giving up.
        Returns:
            A Deferred or a dict containing the chunk data, depending on if
            there was data to return yet. The Deferred callback may be None if
            there were no events before the timeout expired.
        """
        logger.debug("%s is listening for events." % user_id)

        if len(self.stored_event_listeners[user_id]["chunk"]) > 0:
            logger.debug("%s returning existing chunk." % user_id)
            return self.stored_event_listeners[user_id]

        d = defer.Deferred()
        self.stored_event_listeners[user_id]["defer"] = d
        reactor.callLater(timeout, self._timeout, user_id)
        return d

    def _timeout(self, user_id):
        try:
            self.stored_event_listeners[user_id]["defer"].callback(None)
            logger.debug("%s event listening timed out." % user_id)
        except KeyError:
            pass
