# -*- coding: utf-8 -*-
"""Tests REST events for /rooms paths."""

# twisted imports
from twisted.internet import defer

# trial imports
from twisted.trial import unittest

from synapse.api.auth import Auth
import synapse.rest.room
from synapse.api.constants import Membership

from synapse.server import HomeServer

# python imports
import json

from ..utils import MockHttpServer, MemoryDataStore

from mock import Mock


class RoomsTestCase(unittest.TestCase):
    """Contains extra helper functions to quickly and clearly perform a given
    action, which isn't the focus of the test.

    This subclass assumes there are mock_server and auth_user_id attributes.
    """

    def mock_get_user_by_token(self, token=None):
        return self.auth_user_id

    @defer.inlineCallbacks
    def create_room_as(self, room_id, room_creator, is_public=True):
        temp_id = self.auth_user_id
        self.auth_user_id = room_creator
        content = "{}"
        if not is_public:
            content = '{"visibility":"private"}'
        (code, response) = yield self.mock_server.trigger("PUT",
                                "/rooms/%s" % room_id, content)
        self.assertEquals(200, code, msg=str(response))
        self.auth_user_id = temp_id

    @defer.inlineCallbacks
    def invite(self, room=None, src=None, targ=None, expect_code=200):
        yield self.change_membership(room=room, src=src, targ=targ,
                                     membership=Membership.INVITE,
                                     expect_code=expect_code)

    @defer.inlineCallbacks
    def join(self, room=None, user=None, expect_code=200):
        yield self.change_membership(room=room, src=user, targ=user,
                                     membership=Membership.JOIN,
                                     expect_code=expect_code)

    @defer.inlineCallbacks
    def leave(self, room=None, user=None, expect_code=200):
        yield self.change_membership(room=room, src=user, targ=user,
                                     membership=Membership.LEAVE,
                                     expect_code=expect_code)

    @defer.inlineCallbacks
    def change_membership(self, room=None, src=None, targ=None,
                          membership=None, expect_code=200):
        temp_id = self.auth_user_id
        self.auth_user_id = src
        if membership == Membership.LEAVE:
            (code, response) = yield self.mock_server.trigger("DELETE",
                                    "/rooms/%s/members/%s/state" % (room, targ),
                                    None)
            self.assertEquals(expect_code, code, msg=str(response))
        else:
            (code, response) = yield self.mock_server.trigger("PUT",
                                    "/rooms/%s/members/%s/state" % (room, targ),
                                    '{"membership":"%s"}' % membership)
            self.assertEquals(expect_code, code, msg=str(response))

        self.auth_user_id = temp_id


class RoomPermissionsTestCase(RoomsTestCase):
    """ Tests room permissions. """
    user_id = "sid1"
    rmcreator_id = "notme"

    def mock_get_user_by_token(self, token=None):
        return self.auth_user_id

    @defer.inlineCallbacks
    def setUp(self):
        self.mock_server = MockHttpServer()

        hs = HomeServer(
            "test",
            db_pool=None,
            federation=Mock(),
        )
        hs.event_data_store = MemoryDataStore()
        hs.auth = Auth(hs.get_event_data_store())
        hs.auth.get_user_by_token = self.mock_get_user_by_token
        self.auth_user_id = self.rmcreator_id

        synapse.rest.room.register_servlets(hs, self.mock_server)

        self.auth = hs.get_auth()

        # create some rooms under the name rmcreator_id
        self.uncreated_rmid = "aa"

        self.created_rmid = "abc"
        yield self.create_room_as(self.created_rmid, self.rmcreator_id,
                                  is_public=False)

        self.created_public_rmid = "def1234ghi"
        yield self.create_room_as(self.created_public_rmid, self.rmcreator_id,
                                  is_public=True)

        # send a message in one of the rooms
        self.created_rmid_msg_path = ("/rooms/%s/messages/%s/midaaa1" %
                                (self.created_rmid, self.rmcreator_id))
        (code, response) = yield self.mock_server.trigger(
                           "PUT",
                           self.created_rmid_msg_path,
                           '{"msgtype":"sy.text","body":"test msg"}')
        self.assertEquals(200, code, msg=str(response))

        # set topic for public room
        (code, response) = yield self.mock_server.trigger(
                           "PUT",
                           "/rooms/%s/topic" % self.created_public_rmid,
                           '{"topic":"Public Room Topic"}')
        self.assertEquals(200, code, msg=str(response))

        # auth as user_id now
        self.auth_user_id = self.user_id

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def test_get_message(self):
        # get message in uncreated room, expect 403
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/noroom/messages/someid/m1")
        self.assertEquals(403, code, msg=str(response))

        # get message in created room not joined (no state), expect 403
        (code, response) = yield self.mock_server.trigger_get(
                           self.created_rmid_msg_path)
        self.assertEquals(403, code, msg=str(response))

        # get message in created room and invited, expect 403
        yield self.invite(room=self.created_rmid, src=self.rmcreator_id,
                          targ=self.user_id)
        (code, response) = yield self.mock_server.trigger_get(
                           self.created_rmid_msg_path)
        self.assertEquals(403, code, msg=str(response))

        # get message in created room and joined, expect 200
        yield self.join(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger_get(
                           self.created_rmid_msg_path)
        self.assertEquals(200, code, msg=str(response))

        # get message in created room and left, expect 403
        yield self.leave(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger_get(
                           self.created_rmid_msg_path)
        self.assertEquals(403, code, msg=str(response))

    @defer.inlineCallbacks
    def test_send_message(self):
        msg_content = '{"msgtype":"sy.text","body":"hello"}'
        send_msg_path = ("/rooms/%s/messages/%s/mid1" %
                        (self.created_rmid, self.user_id))

        # send message in uncreated room, expect 403
        (code, response) = yield self.mock_server.trigger(
                           "PUT",
                           "/rooms/%s/messages/%s/mid1" %
                           (self.uncreated_rmid, self.user_id), msg_content)
        self.assertEquals(403, code, msg=str(response))

        # send message in created room not joined (no state), expect 403
        (code, response) = yield self.mock_server.trigger(
                           "PUT", send_msg_path, msg_content)
        self.assertEquals(403, code, msg=str(response))

        # send message in created room and invited, expect 403
        yield self.invite(room=self.created_rmid, src=self.rmcreator_id,
                          targ=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", send_msg_path, msg_content)
        self.assertEquals(403, code, msg=str(response))

        # send message in created room and joined, expect 200
        yield self.join(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", send_msg_path, msg_content)
        self.assertEquals(200, code, msg=str(response))

        # send message in created room and left, expect 403
        yield self.leave(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", send_msg_path, msg_content)
        self.assertEquals(403, code, msg=str(response))

    @defer.inlineCallbacks
    def test_topic_perms(self):
        topic_content = '{"topic":"My Topic Name"}'
        topic_path = "/rooms/%s/topic" % self.created_rmid

        # set/get topic in uncreated room, expect 403
        (code, response) = yield self.mock_server.trigger(
                           "PUT", "/rooms/%s/topic" % self.uncreated_rmid,
                           topic_content)
        self.assertEquals(403, code, msg=str(response))
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/%s/topic" % self.uncreated_rmid)
        self.assertEquals(403, code, msg=str(response))

        # set/get topic in created PRIVATE room not joined, expect 403
        (code, response) = yield self.mock_server.trigger(
                           "PUT", topic_path, topic_content)
        self.assertEquals(403, code, msg=str(response))
        (code, response) = yield self.mock_server.trigger_get(topic_path)
        self.assertEquals(403, code, msg=str(response))

        # set topic in created PRIVATE room and invited, expect 403
        yield self.invite(room=self.created_rmid, src=self.rmcreator_id,
                          targ=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", topic_path, topic_content)
        self.assertEquals(403, code, msg=str(response))

        # get topic in created PRIVATE room and invited, expect 200 (or 404)
        (code, response) = yield self.mock_server.trigger_get(topic_path)
        self.assertEquals(404, code, msg=str(response))

        # set/get topic in created PRIVATE room and joined, expect 200
        yield self.join(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", topic_path, topic_content)
        self.assertEquals(200, code, msg=str(response))
        (code, response) = yield self.mock_server.trigger_get(topic_path)
        self.assertEquals(200, code, msg=str(response))
        self.assertEquals(json.loads(topic_content), response)

        # set/get topic in created PRIVATE room and left, expect 403
        yield self.leave(room=self.created_rmid, user=self.user_id)
        (code, response) = yield self.mock_server.trigger(
                           "PUT", topic_path, topic_content)
        self.assertEquals(403, code, msg=str(response))
        (code, response) = yield self.mock_server.trigger_get(topic_path)
        self.assertEquals(403, code, msg=str(response))

        # get topic in PUBLIC room, not joined, expect 200 (or 404)
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/%s/topic" % self.created_public_rmid)
        self.assertEquals(200, code, msg=str(response))

        # set topic in PUBLIC room, not joined, expect 403
        (code, response) = yield self.mock_server.trigger(
                           "PUT",
                           "/rooms/%s/topic" % self.created_public_rmid,
                           topic_content)
        self.assertEquals(403, code, msg=str(response))

    @defer.inlineCallbacks
    def _test_get_membership(self, room=None, members=[], expect_code=None):
        path = "/rooms/%s/members/%s/state"
        for member in members:
            (code, response) = yield self.mock_server.trigger_get(
                               path %
                               (room, member))
            self.assertEquals(expect_code, code)

    @defer.inlineCallbacks
    def test_membership_basic_room_perms(self):
        # === room does not exist ===
        room = self.uncreated_rmid
        # get membership of self, get membership of other, uncreated room
        # expect all 403s
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=403)

        # trying to invite people to this room should 403
        yield self.invite(room=room, src=self.user_id, targ=self.rmcreator_id,
                          expect_code=403)

        # set [invite/join/left] of self, set [invite/join/left] of other,
        # expect all 403s
        for usr in [self.user_id, self.rmcreator_id]:
            yield self.join(room=room, user=usr, expect_code=403)
            yield self.leave(room=room, user=usr, expect_code=403)

    @defer.inlineCallbacks
    def test_membership_private_room_perms(self):
        room = self.created_rmid
        # get membership of self, get membership of other, private room + invite
        # expect all 403s
        yield self.invite(room=room, src=self.rmcreator_id,
                          targ=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=403)

        # get membership of self, get membership of other, private room + joined
        # expect all 200s
        yield self.join(room=room, user=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=200)

        # get membership of self, get membership of other, private room + left
        # expect all 403s
        yield self.leave(room=room, user=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=403)

    @defer.inlineCallbacks
    def test_membership_public_room_perms(self):
        room = self.created_public_rmid
        # get membership of self, get membership of other, public room + invite
        # expect all 403s
        yield self.invite(room=room, src=self.rmcreator_id,
                          targ=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=403)

        # get membership of self, get membership of other, public room + joined
        # expect all 200s
        yield self.join(room=room, user=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=200)

        # get membership of self, get membership of other, public room + left
        # expect all 403s
        yield self.leave(room=room, user=self.user_id)
        yield self._test_get_membership(
            members=[self.user_id, self.rmcreator_id],
            room=room, expect_code=403)

    @defer.inlineCallbacks
    def test_invited_permissions(self):
        room = self.created_rmid
        yield self.invite(room=room, src=self.rmcreator_id, targ=self.user_id)

        # set [invite/join/left] of other user, expect 403s
        yield self.invite(room=room, src=self.user_id, targ=self.rmcreator_id,
                          expect_code=403)
        yield self.change_membership(room=room, src=self.user_id,
                                     targ=self.rmcreator_id,
                                     membership=Membership.JOIN,
                                     expect_code=403)
        yield self.change_membership(room=room, src=self.user_id,
                                     targ=self.rmcreator_id,
                                     membership=Membership.LEAVE,
                                     expect_code=403)

    @defer.inlineCallbacks
    def test_joined_permissions(self):
        room = self.created_rmid
        yield self.invite(room=room, src=self.rmcreator_id, targ=self.user_id)
        yield self.join(room=room, user=self.user_id)

        # set invited of self, expect 403
        yield self.invite(room=room, src=self.user_id, targ=self.user_id,
                          expect_code=403)

        # set joined of self, expect 200 (NOOP)
        yield self.join(room=room, user=self.user_id)

        other = "burgundy"
        # set invited of other, expect 200
        yield self.invite(room=room, src=self.user_id, targ=other,
                          expect_code=200)

        # set joined of other, expect 403
        yield self.change_membership(room=room, src=self.user_id,
                                     targ=other,
                                     membership=Membership.JOIN,
                                     expect_code=403)

        # set left of other, expect 403
        yield self.change_membership(room=room, src=self.user_id,
                                     targ=other,
                                     membership=Membership.LEAVE,
                                     expect_code=403)

        # set left of self, expect 200
        yield self.leave(room=room, user=self.user_id)

    @defer.inlineCallbacks
    def test_leave_permissions(self):
        room = self.created_rmid
        yield self.invite(room=room, src=self.rmcreator_id, targ=self.user_id)
        yield self.join(room=room, user=self.user_id)
        yield self.leave(room=room, user=self.user_id)

        # set [invite/join/left] of self, set [invite/join/left] of other,
        # expect all 403s
        for usr in [self.user_id, self.rmcreator_id]:
            yield self.change_membership(room=room, src=self.user_id,
                                     targ=usr,
                                     membership=Membership.INVITE,
                                     expect_code=403)
            yield self.change_membership(room=room, src=self.user_id,
                                     targ=usr,
                                     membership=Membership.JOIN,
                                     expect_code=403)
            yield self.change_membership(room=room, src=self.user_id,
                                     targ=usr,
                                     membership=Membership.LEAVE,
                                     expect_code=403)


class RoomsMemberListTestCase(RoomsTestCase):
    user_id = "sid1"

    def setUp(self):
        self.mock_server = MockHttpServer()

        hs = HomeServer("test",
                db_pool=None,
                federation=Mock())
        hs.event_data_store = MemoryDataStore()
        self.auth_user_id = self.user_id
        hs.auth = Auth(hs.get_event_data_store())
        hs.auth.get_user_by_token = self.mock_get_user_by_token

        synapse.rest.room.register_servlets(hs, self.mock_server)

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def test_get_member_list(self):
        room_id = "aa"
        yield self.create_room_as(room_id, self.user_id)
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/%s/members/list" % room_id)
        self.assertEquals(200, code, msg=str(response))

    @defer.inlineCallbacks
    def test_get_member_list_no_room(self):
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/roomdoesnotexist/members/list")
        self.assertEquals(403, code, msg=str(response))

    @defer.inlineCallbacks
    def test_get_member_list_no_permission(self):
        room_id = "bb"
        yield self.create_room_as(room_id, "some_other_guy")
        (code, response) = yield self.mock_server.trigger_get(
                           "/rooms/%s/members/list" % room_id)
        self.assertEquals(403, code, msg=str(response))

    @defer.inlineCallbacks
    def test_get_member_list_mixed_memberships(self):
        room_id = "bb"
        room_creator = "some_other_guy"
        room_path = "/rooms/%s/members/list" % room_id
        yield self.create_room_as(room_id, room_creator)
        yield self.invite(room=room_id, src=room_creator,
                          targ=self.user_id)
        # can't see list if you're just invited.
        (code, response) = yield self.mock_server.trigger_get(room_path)
        self.assertEquals(403, code, msg=str(response))

        yield self.join(room=room_id, user=self.user_id)
        # can see list now joined
        (code, response) = yield self.mock_server.trigger_get(room_path)
        self.assertEquals(200, code, msg=str(response))

        yield self.leave(room=room_id, user=self.user_id)
        # can no longer see list, you've left.
        (code, response) = yield self.mock_server.trigger_get(room_path)
        self.assertEquals(403, code, msg=str(response))


class RoomsCreateTestCase(unittest.TestCase):
    """ Tests room creation for /rooms. """
    user_id = "sid1"

    def mock_get_user_by_token(self, token=None):
        return self.user_id

    def setUp(self):
        self.mock_server = MockHttpServer()

        hs = HomeServer(
            "test",
            db_pool=None,
        )
        hs.event_data_store = MemoryDataStore()
        hs.auth = Auth(hs.get_event_data_store())
        hs.auth.get_user_by_token = self.mock_get_user_by_token

        synapse.rest.room.register_servlets(hs, self.mock_server)

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def test_post_room(self):
        # POST with no config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                                          "{}")
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # POST with visibility config key, expect new room id
        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                                '{"visibility":"private"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # POST with custom config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                                '{"custom":"stuff"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # POST with custom + known config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                 '{"visibility":"private","custom":"things"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # POST with invalid content / paths, expect 400
        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                                          '{"visibili')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("POST", "/rooms",
                                                          '["hello"]')
        self.assertEquals(400, code)

    @defer.inlineCallbacks
    def test_put_room(self):
        # PUT with no config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/aa",
                                                          "{}")
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # PUT with known config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/bb",
                                                  '{"visibility":"private"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # PUT with custom config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/cc",
                                               '{"custom":"stuff"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # PUT with custom + known config keys, expect new room id
        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/dd",
                                  '{"visibility":"private","custom":"things"}')
        self.assertEquals(200, code)
        self.assertTrue("room_id" in response)

        # PUT with invalid content / room names, expect 400

        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/ee",
                                                          '{"sdf"')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/ee",
                                                          '["hello"]')
        self.assertEquals(400, code)

        # PUT with conflicting room ID, expect 409
        (code, response) = yield self.mock_server.trigger("PUT", "/rooms/aa",
                                                          "{}")
        self.assertEquals(409, code)


class RoomsTestCase(unittest.TestCase):
    """ Tests /rooms REST events. """
    user_id = "sid1"

    def mock_get_user_by_token(self, token=None):
        return self.user_id

    @defer.inlineCallbacks
    def setUp(self):
        self.mock_server = MockHttpServer()

        hs = HomeServer(
            "test",
            db_pool=None,
            http_server=self.mock_server,
            federation=Mock()
        )
        hs.event_data_store = MemoryDataStore()
        hs.auth = Auth(hs.get_event_data_store())
        hs.auth.get_user_by_token = self.mock_get_user_by_token

        synapse.rest.room.register_servlets(hs, self.mock_server)

        # create the room
        path = "/rooms/rid1"
        (code, response) = yield self.mock_server.trigger("PUT", path, "{}")
        self.assertEquals(200, code)

    def tearDown(self):
        pass

    @defer.inlineCallbacks
    def _test_invalid_puts(self, path):
        # missing keys or invalid json
        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{}')
        self.assertEquals(400, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{"_name":"bob"}')
        self.assertEquals(400, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '{"nao')
        self.assertEquals(400, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '[{"_name":"bob"},{"_name":"jill"}]')
        self.assertEquals(400, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, 'text only')
        self.assertEquals(400, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("PUT",
                           path, '')
        self.assertEquals(400, code, msg=str(response))

    @defer.inlineCallbacks
    def test_rooms_topic(self):
        path = "/rooms/rid1/topic"
        self._test_invalid_puts(path)

        # valid key, wrong type
        content = '{"topic":["Topic name"]}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code, msg=str(response))

        # nothing should be there
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(404, code, msg=str(response))

        # valid put
        content = '{"topic":"Topic name"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code, msg=str(response))

        # valid get
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code, msg=str(response))
        self.assertEquals(json.loads(content), response)

        # valid put with extra keys
        content = '{"topic":"Seasons","subtopic":"Summer"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code, msg=str(response))

        # valid get
        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code, msg=str(response))
        self.assertEquals(json.loads(content), response)

    @defer.inlineCallbacks
    def test_rooms_members_state(self):
        path = "/rooms/rid1/members/%s/state" % self.user_id
        self._test_invalid_puts(path)

        # valid keys, wrong types
        content = ('{"membership":["%s","%s","%s"]}' %
                  (Membership.INVITE, Membership.JOIN, Membership.LEAVE))
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code, msg=str(response))

        # valid join message (NOOP since we made the room)
        content = '{"membership":"%s"}' % Membership.JOIN
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code, msg=str(response))
        self.assertEquals(json.loads(content), response)

    def _assert_dict(self, required, actual):
        for key in required:
            self.assertEquals(required[key], actual[key],
                              msg="%s mismatch. %s" % (key, actual))

    @defer.inlineCallbacks
    def test_rooms_messages_sent(self):
        path = "/rooms/rid1/messages/%s/mid1" % self.user_id
        self._test_invalid_puts(path)

        content = '{"body":"test","msgtype":{"type":"a"}}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(400, code, msg=str(response))

        # custom message types
        content = '{"body":"test","msgtype":"test.custom.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code, msg=str(response))
        self._assert_dict(json.loads(content), response)

        # sy.text message type
        path = "/rooms/rid1/messages/%s/mid2" % self.user_id
        content = '{"body":"test2","msgtype":"sy.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(200, code, msg=str(response))

        (code, response) = yield self.mock_server.trigger("GET", path, None)
        self.assertEquals(200, code, msg=str(response))
        self._assert_dict(json.loads(content), response)

        # trying to send message in different user path
        path = "/rooms/rid1/messages/%s/mid2" % ("invalid" + self.user_id)
        content = '{"body":"test2","msgtype":"sy.text"}'
        (code, response) = yield self.mock_server.trigger("PUT", path, content)
        self.assertEquals(403, code, msg=str(response))
