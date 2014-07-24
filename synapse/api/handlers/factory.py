# -*- coding: utf-8 -*-
from register import RegistrationHandler
from room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from events import EventStreamHandler
from federation import FederationHandler


class EventHandlerFactory(object):

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
