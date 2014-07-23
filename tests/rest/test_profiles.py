# -*- coding: utf-8 -*-
"""Tests REST events for /profile paths."""

from twisted.trial import unittest
from twisted.internet import defer

from ..utils import MockHttpServer

from synapse.server import HomeServer

myid = "!1234ABCD:test"

class ProfilesTestCase(unittest.TestCase):
    """ Tests profile management. """

    def setUp(self):
        self.mock_server = MockHttpServer()

        hs = HomeServer("test",
                db_pool=None,
                http_server=self.mock_server)
        hs.register_servlets()

    @defer.inlineCallbacks
    def test_get_my_name(self):
        (code, response) = yield self.mock_server.trigger("GET",
                "/profile/%s/displayname" % (myid), None)
        self.assertEquals(200, code)
        self.assertEquals("Frank", response)

    @defer.inlineCallbacks
    def test_get_other_name(self):
        (code, response) = yield self.mock_server.trigger("GET",
                "/profile/%s/displayname" % ("!opaque:elsewhere"), None)
        self.assertEquals(200, code)
        self.assertEquals("Bob", response)
