# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock, call
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


class PresencePushTestCase(unittest.TestCase):
    """ Tests steady-state presence status updates.

    They assert that presence state update messages are pushed around the place
    when users change state, presuming that the watches are all established.

    These tests are MASSIVELY fragile currently as they poke internals of the
    presence handler; namely the _user_pushmap and _remote_recvmap.
    BE WARNED...
    """
    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "set_presence_state",
                ]),
                http_server=Mock(),
                http_client=None,
                replication_layer=Mock(spec=[
                    "send_edu",
                ]),
            )

        self.send_edu_mock = hs.get_replication_layer().send_edu
        self.send_edu_mock.return_value = defer.succeed((200, "OK"))

        self.mock_update_client = Mock()
        self.mock_update_client.return_value = defer.succeed(None)

        self.handler = hs.get_handlers().presence_handler
        self.handler.push_update_to_clients = self.mock_update_client

        self.distributor = hs.get_distributor()
        self.distributor.declare("received_edu")

        # Some local users to test with
        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")
        self.u_clementine = hs.parse_userid("@clementine:test")

        # Remote user
        self.u_potato = hs.parse_userid("@potato:remote")

    @defer.inlineCallbacks
    def test_push_local(self):
        # TODO(paul): Gut-wrenching
        apple_set = self.handler._user_pushmap.setdefault("apple", set())
        apple_set.add(self.u_banana)
        apple_set.add(self.u_clementine)

        yield self.handler.set_state(self.u_apple, self.u_apple,
                {"state": PresenceState.ONLINE})

        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_banana,
                    observed_user=self.u_apple,
                    state={"state": PresenceState.ONLINE}),
                call(observer_user=self.u_clementine,
                    observed_user=self.u_apple,
                    state={"state": PresenceState.ONLINE}),
        ], any_order=True)

    @defer.inlineCallbacks
    def test_push_remote(self):
        # TODO(paul): Gut-wrenching
        apple_set = self.handler._user_pushmap.setdefault("apple", set())
        apple_set.add(self.u_potato)

        yield self.handler.set_state(self.u_apple, self.u_apple,
                {"state": PresenceState.ONLINE})

        self.send_edu_mock.assert_called_with(
                destination="remote",
                edu_type="sy.presence",
                content={
                    "push": [
                        {"user_id": "@apple:test",
                         "state": 2},
                    ],
                },
        )

    @defer.inlineCallbacks
    def test_recv_remote(self):
        # TODO(paul): Gut-wrenching
        potato_set = self.handler._remote_recvmap.setdefault(self.u_potato,
                set())
        potato_set.add(self.u_apple)

        yield self.distributor.fire("received_edu",
                "remote", "sy.presence", {
                    "push": [
                        {"user_id": "@potato:remote",
                         "state": 2},
                    ],
                }
        )

        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_apple,
                    observed_user=self.u_potato,
                    state={"state": PresenceState.ONLINE}),
        ])
