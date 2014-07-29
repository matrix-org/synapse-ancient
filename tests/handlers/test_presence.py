# -*- coding: utf-8 -*-

from twisted.trial import unittest
from twisted.internet import defer

from mock import Mock
import logging

from synapse.server import HomeServer


logging.getLogger().addHandler(logging.NullHandler())


class PresenceTestCase(unittest.TestCase):
    """ Tests presence management. """

    def setUp(self):
        hs = HomeServer("test",
                db_pool=None,
                datastore=Mock(spec=[
                    "get_presence_state",
                    "set_presence_state",
                ]),
                http_server=Mock(),
                http_client=None,
            )
        self.datastore = hs.get_datastore()

        self.frank = hs.parse_userid("@1234ABCD:test")

        self.handlers = hs.get_handlers()

    @defer.inlineCallbacks
    def test_get_my_state(self):
        mocked_get = self.datastore.get_presence_state
        mocked_get.return_value = defer.succeed({"state": 2, "status_msg": "Online"})

        state = yield self.handlers.presence_handler.get_state(
                target_user=self.frank, auth_user=self.frank)

        self.assertEquals({"state": 2, "status_msg": "Online"}, state)
        mocked_get.assert_called_with("1234ABCD")

    @defer.inlineCallbacks
    def test_set_my_state(self):
        mocked_set = self.datastore.set_presence_state
        mocked_set.return_value = defer.succeed(())

        yield self.handlers.presence_handler.set_state(
                target_user=self.frank, auth_user=self.frank,
                state={"state": 1, "status_msg": "Away"})

        mocked_set.assert_called_with("1234ABCD",
                {"state": 1, "status_msg": "Away"})
