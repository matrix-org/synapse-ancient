import unittest

from synapse.types import UserID, UserName, RoomName

class MockHomeServer(object):
    def __init__(self):
        self.hostname = "my.domain"

mock_homeserver = MockHomeServer()

class UserIDTestCase(unittest.TestCase):

    def test_parse(self):
        user = UserID.from_string("!1234abcd:my.domain", hs=mock_homeserver)

        self.assertEquals("1234abcd", user.localpart)
        self.assertEquals("my.domain", user.domain)
        self.assertEquals(True, user.is_mine)

    def test_build(self):
        user = UserID("5678efgh", "my.domain", True)

        self.assertEquals(user.to_string(), "!5678efgh:my.domain")


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
