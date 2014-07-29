# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock
import logging

from synapse.server import HomeServer


logging.getLogger().addHandler(logging.NullHandler())


class PresenceStateTestCase(unittest.TestCase):
    """ Tests presence management. """

    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "get_presence_state",
                    "set_presence_state",
                    "allow_presence_inbound",
                    "add_presence_list_pending",
                    "set_presence_list_accepted",
                ]),
                http_server=Mock(),
                http_client=None,
            )
        self.datastore = hs.get_datastore()

        # Some local users to test with
        self.u_apple = hs.parse_userid("@1234ABCD:test")

        self.handlers = hs.get_handlers()

    @defer.inlineCallbacks
    def test_get_my_state(self):
        mocked_get = self.datastore.get_presence_state
        mocked_get.return_value = defer.succeed({"state": 2, "status_msg": "Online"})

        state = yield self.handlers.presence_handler.get_state(
                target_user=self.u_apple, auth_user=self.u_apple)

        self.assertEquals({"state": 2, "status_msg": "Online"}, state)
        mocked_get.assert_called_with("1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_state(self):
        mocked_set = self.datastore.set_presence_state
        mocked_set.return_value = defer.succeed(())

        yield self.handlers.presence_handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": 1, "status_msg": "Away"})

        mocked_set.assert_called_with("1234ABCD",
                {"state": 1, "status_msg": "Away"})


class PresenceInvitesTestCase(unittest.TestCase):
    """ Tests presence management. """

    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "allow_presence_inbound",
                    "add_presence_list_pending",
                    "set_presence_list_accepted",
                ]),
                http_server=Mock(),
                http_client=None,
            )
        self.datastore = hs.get_datastore()

        # Some local users to test with
        self.u_apple = hs.parse_userid("@1234ABCD:test")
        self.u_banana = hs.parse_userid("@2345BCDE:test")

        # A remote user
        self.u_cabbage = hs.parse_userid("@someone:elsewhere")

        self.handlers = hs.get_handlers()

    @defer.inlineCallbacks
    def test_invite_local(self):
        # TODO(paul): This test will likely break if/when real auth permissions
        # are added; for now the HS will always accept any invite

        yield self.handlers.presence_handler.send_invite(
                observer_user=self.u_apple, observed_user=self.u_banana)

        self.datastore.add_presence_list_pending.assert_called_with(
                "1234ABCD", "@2345BCDE:test")
        self.datastore.allow_presence_inbound.assert_called_with(
                "2345BCDE", "@1234ABCD:test")
        self.datastore.set_presence_list_accepted.assert_called_with(
                "1234ABCD", "@2345BCDE:test")
