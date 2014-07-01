from twistar.dbobject import DBObject

class Message(DBObject):
    """ A user-initiated message.

    This refers to messages sent between humans, rather than meta-messages like
    presence, room metadata, etc.
    """
    TEXT = "text"

class Presence(DBObject):
    """ A presence event. """
    TYPE = "presence"

class RoomMembership(DBObject):
    """ A room membership change event. """
    TYPE = "room_membership"
