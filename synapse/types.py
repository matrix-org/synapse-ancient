# -*- coding: utf-8 -*-

def split_localpart_domain(s, sigil):
    """Splits a string of the form "{SIGIL}localpart:domain" into its local
    and domain parts and returns them. Requires that the first character of
    the string be the given sigil."""
    if s[0] != sigil:
        raise ValueError("Expected '%s' to start with '%s'" % (s, sigil))

    parts = s[1:].split(':')
    if len(parts) != 2:
        raise ValueError("Expected '%s' of the form '%slocalname:domain'" %
                (s, sigil))

    return parts[0], parts[1]


class DomainSpecificString(object):
    """Common base class among ID/name strings that have a local part and a
    domain name, prefixed with a sigil.

    Has the fields:

        'localpart' : The local part of the name (without the leading sigil)
        'domain' : The domain part of the name
        'is_mine' : Boolean indicating if the domain name is recognised by the
            HomeServer as being its own
    """

    def __init__(self, localpart, domain, is_mine):
        self.localpart = localpart
        self.domain = domain
        self.is_mine = is_mine

    @classmethod
    def from_string(cls, s, hs):
        """Parse the string given by 's' into a structure object."""
        localpart, domain = split_localpart_domain(s, cls.SIGIL)

        # This code will need changing if we want to support multiple domain
        # names on one HS
        is_mine = domain == hs.hostname
        return cls(localpart=localpart, domain=domain, is_mine=is_mine)

    def to_string(self):
        """Return a string encoding the fields of the structure object."""
        return "%s%s:%s" % (self.SIGIL, self.localpart, self.domain)


class UserID(DomainSpecificString):
    """Structure representing a user ID."""
    SIGIL = "!"


class UserName(DomainSpecificString):
    """Structure representing a user name."""
    SIGIL = "@"


class RoomName(DomainSpecificString):
    """Structure representing a room name."""
    SIGIL = "#"
