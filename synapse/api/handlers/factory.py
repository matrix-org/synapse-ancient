# -*- coding: utf-8 -*-
from register import RegistrationHandler
from room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from synapse.util.dbutils import DbPool  # TODO remove


class EventHandlerFactory(object):

    """ A factory for creating synapse event handlers.
    """

    def __init__(self, event_store, event_factory):
        self.store = event_store
        self.event_factory = event_factory

    def register_handler(self):
        return RegistrationHandler(db_pool=DbPool.get())  # TODO remove dbpool

    def message_handler(self):
        return MessageHandler(self.store, self.event_factory)

    def room_creation_handler(self):
        return RoomCreationHandler(self.store, self.event_factory)

    def room_member_handler(self):
        return RoomMemberHandler(self.store, self.event_factory)