# -*- coding: utf-8 -*-
from synapse.api.events.room import MessageEvent, RoomCreationEvent
from synapse.api.events.register import RegistrationEvent
from synapse.util.dbutils import DbPool  # TODO remove


class EventFactory(object):

    """ A factory for creating synapse events.

    Synapse events are logical entities which process a single event, such as
    sending a message, setting a room topic, etc. These may be wrapped by REST
    events to provide a way for clients to initiate events.

    See synapse.rest.base for information on synapse REST events.
    """

    def __init__(self, event_store):
        self.store = event_store

    def register_event(self):
        """Create a registration event."""
        return RegistrationEvent(db_pool=DbPool.get())  # TODO remove dbpool

    def message_event(self):
        return MessageEvent(self.store)

    def room_creation_event(self):
        return RoomCreationEvent(self.store)

