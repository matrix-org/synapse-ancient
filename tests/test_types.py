import unittest

from synapse.server import BaseHomeServer
from synapse.types import UserID, UserName, RoomName

mock_homeserver = BaseHomeServer(hostname="my.domain")

class UserIDTestCase(unittest.TestCase):

    def test_parse(self):
        user = UserID.from_string("!1234abcd:my.domain", hs=mock_homeserver)

        self.assertEquals("1234abcd", user.localpart)
        self.assertEquals("my.domain", user.domain)
        self.assertEquals(True, user.is_mine)

    def test_build(self):
        user = UserID("5678efgh", "my.domain", True)

        self.assertEquals(user.to_string(), "!5678efgh:my.domain")

    def test_via_homeserver(self):
        user = mock_homeserver.parse_userid("!3456ijkl:my.domain")

        self.assertEquals("3456ijkl", user.localpart)
        self.assertEquals("my.domain", user.domain)


class UserNameTestCase(unittest.TestCase):

    def test_parse(self):
        user = UserName.from_string("@Frank:my.domain", hs=mock_homeserver)

        self.assertEquals("Frank", user.localpart)
        self.assertEquals("my.domain", user.domain)
        self.assertEquals(True, user.is_mine)

    def test_build(self):
        user = UserName("Frank", "my.domain", True)

        self.assertEquals(user.to_string(), "@Frank:my.domain")


class RoomNameTestCase(unittest.TestCase):

    def test_parse(self):
        user = RoomName.from_string("#channel:my.domain", hs=mock_homeserver)

        self.assertEquals("channel", user.localpart)
        self.assertEquals("my.domain", user.domain)
        self.assertEquals(True, user.is_mine)

    def test_build(self):
        user = RoomName("channel", "my.domain", True)

        self.assertEquals(user.to_string(), "#channel:my.domain")
