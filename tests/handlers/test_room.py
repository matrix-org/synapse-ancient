# -*- coding: utf-8 -*-

from twisted.internet import defer
from twisted.trial import unittest

from synapse.api.events.room import (
    InviteJoinEvent, MessageEvent, RoomMemberEvent
)
from synapse.api.constants import Membership
from synapse.handlers.room import RoomMemberHandler
from synapse.server import HomeServer

from mock import NonCallableMock

import logging

logging.getLogger().addHandler(logging.NullHandler())


class RoomMemberHandlerTestCase(unittest.TestCase):

    def setUp(self):
        self.hostname = "red"
        hs = HomeServer(
            self.hostname,
            db_pool=None,
            datastore=NonCallableMock(spec_set=[
                "store_room_member",
                "get_joined_hosts_for_room",
                "get_room_member",
                "get_room",
                "store_room",
            ]),
            http_server=NonCallableMock(),
            http_client=NonCallableMock(spec_set=[]),
            notifier=NonCallableMock(spec_set=["on_new_event"]),
            handlers=NonCallableMock(spec_set=[
                "room_member_handler",
            ]),
            auth=NonCallableMock(spec_set=["check"]),
            federation=NonCallableMock(spec_set=[
                "handle_new_event",
                "get_state_for_room",
            ]),
            state_handler=NonCallableMock(spec_set=["handle_new_event"]),
        )

        self.datastore = hs.get_datastore()
        self.handlers = hs.get_handlers()
        self.notifier = hs.get_notifier()
        self.federation = hs.get_federation()
        self.state_handler = hs.get_state_handler()
        self.hs = hs

        self.handlers.room_member_handler = RoomMemberHandler(self.hs)
        self.room_member_handler = self.handlers.room_member_handler

    @defer.inlineCallbacks
    def test_invite(self):
        room_id = "foo"
        user_id = "@bob:red"
        target_user_id = "@red:blue"
        content = {"membership": Membership.INVITE}

        event = self.hs.get_event_factory().create_event(
            etype=RoomMemberEvent.TYPE,
            user_id=user_id,
            target_user_id=target_user_id,
            room_id=room_id,
            membership=Membership.INVITE,
            content=content,
        )

        joined = ["red", "green"]

        self.state_handler.handle_new_event.return_value = defer.succeed(True)
        self.datastore.get_joined_hosts_for_room.return_value = (
            defer.succeed(joined)
        )

        store_id = "store_id_fooo"
        self.datastore.store_room_member.return_value = defer.succeed(store_id)

        yield self.room_member_handler.change_membership(event)

        self.state_handler.handle_new_event.assert_called_once_with(event)
        self.federation.handle_new_event.assert_called_once_with(event)

        self.assertEquals(
            set(["blue", "red", "green"]),
            set(event.destinations)
        )

        self.datastore.store_room_member.assert_called_once_with(
            user_id=target_user_id,
            sender=user_id,
            room_id=room_id,
            content=content,
            membership=Membership.INVITE,
        )
        self.notifier.on_new_event.assert_called_once_with(event, store_id)

        self.assertFalse(self.datastore.get_room_member.called)
        self.assertFalse(self.datastore.get_room.called)
        self.assertFalse(self.datastore.store_room.called)
        self.assertFalse(self.federation.get_state_for_room.called)

    @defer.inlineCallbacks
    def test_simple_join(self):
        room_id = "foo"
        user_id = "@bob:red"
        target_user_id = "@bob:red"
        content = {"membership": Membership.JOIN}

        event = self.hs.get_event_factory().create_event(
            etype=RoomMemberEvent.TYPE,
            user_id=user_id,
            target_user_id=target_user_id,
            room_id=room_id,
            membership=Membership.JOIN,
            content=content,
        )

        joined = ["red", "green"]

        self.state_handler.handle_new_event.return_value = defer.succeed(True)
        self.datastore.get_joined_hosts_for_room.return_value = (
            defer.succeed(joined)
        )

        store_id = "store_id_fooo"
        self.datastore.store_room_member.return_value = defer.succeed(store_id)
        self.datastore.get_room.return_value = defer.succeed(1)  # Not None.

        prev_state = NonCallableMock()
        prev_state.membership = Membership.INVITE
        prev_state.sender = "@foo:red"
        self.datastore.get_room_member.return_value = defer.succeed(prev_state)

        yield self.room_member_handler.change_membership(event)

        self.state_handler.handle_new_event.assert_called_once_with(event)
        self.federation.handle_new_event.assert_called_once_with(event)

        self.assertEquals(
            set(["red", "green"]),
            set(event.destinations)
        )

        self.datastore.store_room_member.assert_called_once_with(
            user_id=target_user_id,
            sender=user_id,
            room_id=room_id,
            content=content,
            membership=Membership.JOIN,
        )
        self.notifier.on_new_event.assert_called_once_with(event, store_id)

    @defer.inlineCallbacks
    def test_invite_join(self):
        room_id = "foo"
        user_id = "@bob:red"
        target_user_id = "@bob:red"
        content = {"membership": Membership.JOIN}

        event = self.hs.get_event_factory().create_event(
            etype=RoomMemberEvent.TYPE,
            user_id=user_id,
            target_user_id=target_user_id,
            room_id=room_id,
            membership=Membership.JOIN,
            content=content,
        )

        joined = ["red", "blue", "green"]

        self.state_handler.handle_new_event.return_value = defer.succeed(True)
        self.datastore.get_joined_hosts_for_room.return_value = (
            defer.succeed(joined)
        )

        store_id = "store_id_fooo"
        self.datastore.store_room_member.return_value = defer.succeed(store_id)
        self.datastore.get_room.return_value = defer.succeed(None)

        prev_state = NonCallableMock(name="prev_state")
        prev_state.membership = Membership.INVITE
        prev_state.sender = "@foo:blue"
        self.datastore.get_room_member.return_value = defer.succeed(prev_state)

        yield self.room_member_handler.change_membership(event)

        self.datastore.get_room_member.assert_called_once_with(
            target_user_id, room_id
        )

        self.assertTrue(self.federation.handle_new_event.called)
        args = self.federation.handle_new_event.call_args[0]
        invite_join_event = args[0]

        self.assertTrue(InviteJoinEvent.TYPE, invite_join_event.TYPE)
        self.assertTrue(prev_state.sender, invite_join_event.target_user_id)
        self.assertTrue(room_id, invite_join_event.room_id)
        self.assertTrue(user_id, invite_join_event.user_id)
        self.assertFalse(hasattr(invite_join_event, "state_key"))

        self.assertEquals(
            set(["blue"]),
            set(invite_join_event.destinations)
        )

        self.federation.get_state_for_room.assert_called_once_with(
            "blue", room_id
        )

        self.assertFalse(self.datastore.store_room_member.called)

        self.assertFalse(self.notifier.on_new_event.called)
        self.assertFalse(self.state_handler.handle_new_event.called)
