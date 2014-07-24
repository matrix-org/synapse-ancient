# -*- coding: utf-8 -*-
from .handlers.register import RegistrationHandler
from .handlers.room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from .handlers.events import EventStreamHandler
from .handlers.federation import FederationHandler


class HandlerFactory(object):

    """ A factory for creating synapse event handlers.
    """

    def __init__(self, hs):
        self.hs = hs

    def registration_handler(self):
        return RegistrationHandler(self.hs)

    def message_handler(self):
        return MessageHandler(self.hs)

    def room_creation_handler(self):
        return RoomCreationHandler(self.hs)

    def room_member_handler(self):
        return RoomMemberHandler(self.hs)

    def event_stream_handler(self):
        return EventStreamHandler(self.hs)

    def federation_handler(self):
        return FederationHandler(self.hs)
