# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock
import logging

from synapse.server import HomeServer
from synapse.api.constants import PresenceState


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
        self.u_apple = hs.parse_userid("@apple:test")

        self.handlers = hs.get_handlers()

        self.mock_start = Mock()
        self.mock_stop = Mock()

        self.handlers.presence_handler.start_polling_presence = self.mock_start
        self.handlers.presence_handler.stop_polling_presence = self.mock_stop

    @defer.inlineCallbacks
    def test_get_my_state(self):
        mocked_get = self.datastore.get_presence_state
        mocked_get.return_value = defer.succeed({"state": 2, "status_msg": "Online"})

        state = yield self.handlers.presence_handler.get_state(
                target_user=self.u_apple, auth_user=self.u_apple)

        self.assertEquals({"state": 2, "status_msg": "Online"}, state)
        mocked_get.assert_called_with("apple")

    @defer.inlineCallbacks
    def test_set_my_state_online(self):
        mocked_set = self.datastore.set_presence_state
        mocked_set.return_value = defer.succeed((PresenceState.OFFLINE))

        yield self.handlers.presence_handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": PresenceState.BUSY, "status_msg": "Away"})

        mocked_set.assert_called_with("apple",
                {"state": 1, "status_msg": "Away"})
        self.mock_start.assert_called_with(self.u_apple)

    @defer.inlineCallbacks
    def test_set_my_state_offline(self):
        mocked_set = self.datastore.set_presence_state
        mocked_set.return_value = defer.succeed((PresenceState.ONLINE))

        yield self.handlers.presence_handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": PresenceState.OFFLINE})

        self.mock_stop.assert_called_with(self.u_apple)


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
                replication_layer=Mock(spec=[
                    "send_edu",
                ]),
            )
        self.datastore = hs.get_datastore()
        self.send_edu_mock = hs.get_replication_layer().send_edu

        # Some local users to test with
        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")

        # A remote user
        self.u_cabbage = hs.parse_userid("@cabbage:elsewhere")

        self.handlers = hs.get_handlers()

        self.distributor = hs.get_distributor()
        self.distributor.declare("received_edu")

        self.mock_start = Mock()
        self.mock_stop = Mock()

        self.handlers.presence_handler.start_polling_presence = self.mock_start
        self.handlers.presence_handler.stop_polling_presence = self.mock_stop

    @defer.inlineCallbacks
    def test_invite_local(self):
        # TODO(paul): This test will likely break if/when real auth permissions
        # are added; for now the HS will always accept any invite

        yield self.handlers.presence_handler.send_invite(
                observer_user=self.u_apple, observed_user=self.u_banana)

        self.datastore.add_presence_list_pending.assert_called_with(
                "apple", "@banana:test")
        self.datastore.allow_presence_inbound.assert_called_with(
                "banana", "@apple:test")
        self.datastore.set_presence_list_accepted.assert_called_with(
                "apple", "@banana:test")

        self.mock_start.assert_called_with(
                self.u_apple, target_user=self.u_banana)

    @defer.inlineCallbacks
    def test_invite_remote(self):
        self.send_edu_mock.return_value = defer.succeed((200, "OK"))

        yield self.handlers.presence_handler.send_invite(
                observer_user=self.u_apple, observed_user=self.u_cabbage)

        self.datastore.add_presence_list_pending.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.send_edu_mock.assert_called_with(
                destination="elsewhere",
                edu_type="sy.presence_invite",
                content={
                    "observer_user": "@apple:test",
                    "observed_user": "@cabbage:elsewhere",
                }
        )

    @defer.inlineCallbacks
    def test_accept_remote(self):
        # TODO(paul): This test will likely break if/when real auth permissions
        # are added; for now the HS will always accept any invite
        self.send_edu_mock.return_value = defer.succeed((200, "OK"))

        yield self.distributor.fire("received_edu",
                "elsewhere", "sy.presence_invite", {
                    "observer_user": "@cabbage:elsewhere",
                    "observed_user": "@apple:test",
                }
        )

        self.datastore.allow_presence_inbound.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.send_edu_mock.assert_called_with(
                destination="elsewhere",
                edu_type="sy.presence_accept",
                content={
                    "observer_user": "@cabbage:elsewhere",
                    "observed_user": "@apple:test",
                }
        )

    @defer.inlineCallbacks
    def test_accepted_remote(self):
        yield self.distributor.fire("received_edu",
                "elsewhere", "sy.presence_accept", {
                    "observer_user": "@apple:test",
                    "observed_user": "@cabbage:elsewhere",
                }
        )

        self.datastore.set_presence_list_accepted.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.mock_start.assert_called_with(
                self.u_apple, target_user=self.u_cabbage)
