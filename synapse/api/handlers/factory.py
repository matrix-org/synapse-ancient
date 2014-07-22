# -*- coding: utf-8 -*-
from register import RegistrationHandler
from room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from events import EventStreamHandler
from federation import FederationHandler


class EventHandlerFactory(object):

    """ A factory for creating synapse event handlers.
    """

    def __init__(self, hs):
        self.store = hs.get_event_data_store()
        self.event_factory = hs.get_event_factory()
        self.auth = hs.get_auth()
        self.notifier = hs.get_notifier()

    def register_handler(self):
        return RegistrationHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)

    def message_handler(self):
        return MessageHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)

    def room_creation_handler(self):
        return RoomCreationHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)

    def room_member_handler(self):
        return RoomMemberHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)

    def event_stream_handler(self):
        return EventStreamHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)

    def federation_handler(self):
        return FederationHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=self.notifier,
            auth=self.auth)
