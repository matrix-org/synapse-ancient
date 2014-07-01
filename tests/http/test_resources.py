""" Tests web resources can be called and stuff is actually returned. """
# twisted imports
from twisted.internet.defer import Deferred
from twisted.internet import defer

# twistar imports
from twistar.dbobject import DBObject

# trial imports
from twisted.trial import unittest

from synapse.http.resources import SynapseResource
from synapse.util.web_test_utils import DummySite

from mock import patch, Mock

class EventsTest(unittest.TestCase):

    @patch('synapse.api.core.SynapseApi')
    def setUp(self, synapi):
        self.web = DummySite(SynapseResource(synapi))

    @defer.inlineCallbacks
    def test_get(self):
        response = yield self.web.get("/events")
