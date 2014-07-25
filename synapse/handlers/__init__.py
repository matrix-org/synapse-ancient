# -*- coding: utf-8 -*-
from .register import RegistrationHandler
from .room import MessageHandler, RoomCreationHandler, RoomMemberHandler
from .events import EventStreamHandler
from .federation import FederationHandler
from .profile import ProfileHandler


class Handlers(object):

    """ A collection of all the event handlers.

    There's no need to lazily create these; we'll just make them all eagerly
    at construction time.
    """

    def __init__(self, hs):
        self.registration_handler = RegistrationHandler(hs)
        self.message_handler = MessageHandler(hs)
        self.room_creation_handler = RoomCreationHandler(hs)
        self.room_member_handler = RoomMemberHandler(hs)
        self.event_stream_handler = EventStreamHandler(hs)
        self.federation_handler = FederationHandler(hs)
        self.profile_handler = ProfileHandler(hs)
