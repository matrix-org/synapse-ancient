# -*- coding: utf-8 -*-
"""Contains constants from the specification."""


class Membership(object):

    """Represents the membership states of a user in a room."""
    INVITE = u"invite"
    JOIN = u"join"
    KNOCK = u"knock"
    LEAVE = u"leave"


class Feedback(object):

    """Represents the types of feedback a user can send in response to a
    message."""

    DELIVERED = u"d"
    READ = u"r"
    LIST = (DELIVERED, READ)


class PresenceState(object):
    """Represents the presence state of a user."""
    OFFLINE = 0
    BUSY = 1
    ONLINE = 2
    FREE_FOR_CHAT = 3
