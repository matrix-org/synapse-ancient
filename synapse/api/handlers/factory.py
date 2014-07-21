# -*- coding: utf-8 -*-
from register import RegistrationHandler
from room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from events import EventStreamHandler


class EventHandlerFactory(object):

    """ A factory for creating synapse event handlers.
    """

    def __init__(self, store, event_factory, auth):
        self.store = store
        self.event_factory = event_factory
        self.auth = auth

    def register_handler(self):
        return RegistrationHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=None,
            auth=self.auth)

    def message_handler(self):
        return MessageHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=None,
            auth=self.auth)

    def room_creation_handler(self):
        return RoomCreationHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=None,
            auth=self.auth)

    def room_member_handler(self):
        return RoomMemberHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=None,
            auth=self.auth)

    def event_stream_handler(self):
        return EventStreamHandler(
            store=self.store,
            ev_factory=self.event_factory,
            notifier=None,
            auth=self.auth)