# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock, call
import logging

from synapse.server import HomeServer
from synapse.api.constants import PresenceState


OFFLINE = PresenceState.OFFLINE
BUSY = PresenceState.BUSY
ONLINE = PresenceState.ONLINE


logging.getLogger().addHandler(logging.NullHandler())


class MockReplication(object):
    def __init__(self):
        self.edu_handlers = {}

    def register_edu_handler(self, edu_type, handler):
        self.edu_handlers[edu_type] = handler

    def received_edu(self, origin, edu_type, content):
        self.edu_handlers[edu_type](origin, content)


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
        mocked_set.return_value = defer.succeed((OFFLINE))

        yield self.handlers.presence_handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": BUSY, "status_msg": "Away"})

        mocked_set.assert_called_with("apple",
                {"state": 1, "status_msg": "Away"})
        self.mock_start.assert_called_with(self.u_apple)

    @defer.inlineCallbacks
    def test_set_my_state_offline(self):
        mocked_set = self.datastore.set_presence_state
        mocked_set.return_value = defer.succeed((ONLINE))

        yield self.handlers.presence_handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": OFFLINE})

        self.mock_stop.assert_called_with(self.u_apple)


class PresenceInvitesTestCase(unittest.TestCase):
    """ Tests presence management. """

    def setUp(self):
        self.replication = MockReplication()
        self.replication.send_edu = Mock()

        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "allow_presence_inbound",
                    "add_presence_list_pending",
                    "set_presence_list_accepted",
                    "get_presence_list",
                ]),
                http_server=Mock(),
                http_client=None,
                replication_layer=self.replication
            )
        self.datastore = hs.get_datastore()

        # Some local users to test with
        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")

        # A remote user
        self.u_cabbage = hs.parse_userid("@cabbage:elsewhere")

        self.handlers = hs.get_handlers()

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
        self.replication.send_edu.return_value = defer.succeed((200, "OK"))

        yield self.handlers.presence_handler.send_invite(
                observer_user=self.u_apple, observed_user=self.u_cabbage)

        self.datastore.add_presence_list_pending.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.replication.send_edu.assert_called_with(
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
        self.replication.send_edu.return_value = defer.succeed((200, "OK"))

        yield self.replication.received_edu(
                "elsewhere", "sy.presence_invite", {
                    "observer_user": "@cabbage:elsewhere",
                    "observed_user": "@apple:test",
                }
        )

        self.datastore.allow_presence_inbound.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.replication.send_edu.assert_called_with(
                destination="elsewhere",
                edu_type="sy.presence_accept",
                content={
                    "observer_user": "@cabbage:elsewhere",
                    "observed_user": "@apple:test",
                }
        )

    @defer.inlineCallbacks
    def test_accepted_remote(self):
        yield self.replication.received_edu(
                "elsewhere", "sy.presence_accept", {
                    "observer_user": "@apple:test",
                    "observed_user": "@cabbage:elsewhere",
                }
        )

        self.datastore.set_presence_list_accepted.assert_called_with(
                "apple", "@cabbage:elsewhere")

        self.mock_start.assert_called_with(
                self.u_apple, target_user=self.u_cabbage)


    @defer.inlineCallbacks
    def test_get_presence_list(self):
        self.datastore.get_presence_list.return_value = defer.succeed(
                [{"observed_user_id": "@banana:test"}]
        )

        presence = yield self.handlers.presence_handler.get_presence_list(
                observer_user=self.u_apple)

        self.assertEquals([self.u_banana], presence)

        self.datastore.get_presence_list.assert_called_with("apple",
                accepted=None)


        self.datastore.get_presence_list.return_value = defer.succeed(
                [{"observed_user_id": "@banana:test"}]
        )

        presence = yield self.handlers.presence_handler.get_presence_list(
                observer_user=self.u_apple, accepted=True)

        self.assertEquals([self.u_banana], presence)

        self.datastore.get_presence_list.assert_called_with("apple",
                accepted=True)


class PresencePushTestCase(unittest.TestCase):
    """ Tests steady-state presence status updates.

    They assert that presence state update messages are pushed around the place
    when users change state, presuming that the watches are all established.

    These tests are MASSIVELY fragile currently as they poke internals of the
    presence handler; namely the _local_pushmap and _remote_recvmap.
    BE WARNED...
    """
    def setUp(self):
        self.replication = MockReplication()
        self.replication.send_edu = Mock()
        self.replication.send_edu.return_value = defer.succeed((200, "OK"))

        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "set_presence_state",
                ]),
                http_server=Mock(),
                http_client=None,
                replication_layer=self.replication,
            )

        self.mock_update_client = Mock()
        self.mock_update_client.return_value = defer.succeed(None)

        self.handler = hs.get_handlers().presence_handler
        self.handler.push_update_to_clients = self.mock_update_client

        # Some local users to test with
        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")
        self.u_clementine = hs.parse_userid("@clementine:test")

        # Remote user
        self.u_potato = hs.parse_userid("@potato:remote")

    @defer.inlineCallbacks
    def test_push_local(self):
        # TODO(paul): Gut-wrenching
        apple_set = self.handler._local_pushmap.setdefault("apple", set())
        apple_set.add(self.u_banana)
        apple_set.add(self.u_clementine)

        yield self.handler.set_state(self.u_apple, self.u_apple,
                {"state": ONLINE})

        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_banana,
                    observed_user=self.u_apple,
                    state={"state": ONLINE}),
                call(observer_user=self.u_clementine,
                    observed_user=self.u_apple,
                    state={"state": ONLINE}),
        ], any_order=True)

    @defer.inlineCallbacks
    def test_push_remote(self):
        # TODO(paul): Gut-wrenching
        apple_set = self.handler._remote_sendmap.setdefault("apple", set())
        apple_set.add(self.u_potato.domain)

        yield self.handler.set_state(self.u_apple, self.u_apple,
                {"state": ONLINE})

        self.replication.send_edu.assert_called_with(
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

        yield self.replication.received_edu(
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
                    state={"state": ONLINE}),
        ])


class PresencePollingTestCase(unittest.TestCase):
    """ Tests presence status polling. """

    # For this test, we have three local users; apple is watching and is
    # watched by the other two, but the others don't watch each other.
    # Additionally clementine is watching a remote user.
    PRESENCE_LIST = {
            'apple': [ "@banana:test", "@clementine:test" ],
            'banana': [ "@apple:test" ],
            'clementine': [ "@apple:test", "@potato:remote" ],
    }


    def setUp(self):
        self.replication = MockReplication()
        self.replication.send_edu = Mock()

        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[]),
                http_server=Mock(),
                http_client=None,
                replication_layer=self.replication,
            )
        self.datastore = hs.get_datastore()

        self.mock_update_client = Mock()
        self.mock_update_client.return_value = defer.succeed(None)

        self.handler = hs.get_handlers().presence_handler
        self.handler.push_update_to_clients = self.mock_update_client

        # Mocked database state
        # Local users always start offline
        self.current_user_state = {
                "apple": OFFLINE,
                "banana": OFFLINE,
                "clementine": OFFLINE,
        }

        def get_presence_state(user_localpart):
            return defer.succeed(
                    {"state": self.current_user_state[user_localpart]}
            )
        self.datastore.get_presence_state = get_presence_state

        def set_presence_state(user_localpart, new_state):
            was = self.current_user_state[user_localpart]
            self.current_user_state[user_localpart] = new_state["state"]
            return defer.succeed(was)
        self.datastore.set_presence_state = set_presence_state

        def get_presence_list(user_localpart, accepted):
            return defer.succeed([
                {"observed_user_id": u} for u in
                self.PRESENCE_LIST[user_localpart]])
        self.datastore.get_presence_list = get_presence_list

        # Local users
        self.u_apple = hs.parse_userid("@apple:test")
        self.u_banana = hs.parse_userid("@banana:test")
        self.u_clementine = hs.parse_userid("@clementine:test")

        # Remote users
        self.u_potato = hs.parse_userid("@potato:remote")

    @defer.inlineCallbacks
    def test_push_local(self):
        # apple goes online
        yield self.handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": ONLINE})

        # apple should see both banana and clementine currently offline
        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_apple,
                    observed_user=self.u_banana,
                    state={"state": OFFLINE}),
                call(observer_user=self.u_apple,
                    observed_user=self.u_clementine,
                    state={"state": OFFLINE}),
        ], any_order=True)

        # Gut-wrenching tests
        self.assertTrue("banana" in self.handler._local_pushmap)
        self.assertTrue(self.u_apple in self.handler._local_pushmap["banana"])
        self.assertTrue("clementine" in self.handler._local_pushmap)
        self.assertTrue(self.u_apple in self.handler._local_pushmap["clementine"])

        self.mock_update_client.reset_mock()

        # banana goes online
        yield self.handler.set_state(
                target_user=self.u_banana, auth_user=self.u_banana,
                state={"state": ONLINE})

        # apple and banana should now both see each other online
        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_apple,
                    observed_user=self.u_banana,
                    state={"state": ONLINE}),
                call(observer_user=self.u_banana,
                    observed_user=self.u_apple,
                    state={"state": ONLINE}),
        ], any_order=True)

        self.assertTrue("apple" in self.handler._local_pushmap)
        self.assertTrue(self.u_banana in self.handler._local_pushmap["apple"])

        self.mock_update_client.reset_mock()

        # apple goes offline
        yield self.handler.set_state(
                target_user=self.u_apple, auth_user=self.u_apple,
                state={"state": OFFLINE})

        # banana should now be told apple is offline
        self.mock_update_client.assert_has_calls([
                call(observer_user=self.u_banana,
                    observed_user=self.u_apple,
                    state={"state": OFFLINE}),
        ], any_order=True)

        self.assertFalse("banana" in self.handler._local_pushmap)
        self.assertFalse("clementine" in self.handler._local_pushmap)

    @defer.inlineCallbacks
    def test_remote_poll_send(self):
        # clementine goes online
        yield self.handler.set_state(
                target_user=self.u_clementine, auth_user=self.u_clementine,
                state={"state": ONLINE})

        self.replication.send_edu.assert_called_with(
                destination="remote",
                edu_type="sy.presence",
                content={
                    "poll": [ "@potato:remote" ],
                },
        )

        # Gut-wrenching tests
        self.assertTrue(self.u_potato in self.handler._remote_recvmap)
        self.assertTrue(self.u_clementine in
                self.handler._remote_recvmap[self.u_potato])

        self.replication.send_edu.reset_mock()

        # clementine goes offline
        yield self.handler.set_state(
                target_user=self.u_clementine, auth_user=self.u_clementine,
                state={"state": OFFLINE})

        self.replication.send_edu.assert_called_with(
                destination="remote",
                edu_type="sy.presence",
                content={
                    "unpoll": [ "@potato:remote" ],
                },
        )

        self.assertFalse(self.u_potato in self.handler._remote_recvmap)

    @defer.inlineCallbacks
    def test_remote_poll_receive(self):
        yield self.replication.received_edu(
                "remote", "sy.presence", {
                    "poll": [ "@banana:test" ],
                }
        )

        # Gut-wrenching tests
        self.assertTrue(self.u_banana in self.handler._remote_sendmap)

        self.replication.send_edu.assert_called_with(
                destination="remote",
                edu_type="sy.presence",
                content={
                    "push": [
                        {"user_id": "@banana:test", "state": 0},
                    ],
                },
        )

        yield self.replication.received_edu(
                "remote", "sy.presence", {
                    "unpoll": [ "@banana:test" ],
                }
        )

        # Gut-wrenching tests
        self.assertFalse(self.u_banana in self.handler._remote_sendmap)
