# -*- coding: utf-8 -*-
from twistar.dbobject import DBObject


class Message(DBObject):

    """ A user-initiated message.

    This refers to messages sent between humans, rather than meta-messages like
    presence, room metadata, etc.
    """
    TABLENAME = "messages"

