# -*- coding: utf-8 -*-
from register import RegistrationHandler
from room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from synapse.util.dbutils import DbPool  # TODO remove


class EventHandlerFactory(object):

    """ A factory for creating synapse event handlers.
    """

    def __init__(self, event_store, event_factory, auth):
        self.store = event_store
        self.event_factory = event_factory
        self.auth = auth

    def register_handler(self):
        return RegistrationHandler(db_pool=DbPool.get())  # TODO remove dbpool

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