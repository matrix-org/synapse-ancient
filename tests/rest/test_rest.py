# twisted imports
from twisted.enterprise import adbapi
from twisted.internet import defer

# trial imports
from twistar.registry import Registry
from twisted.trial import unittest

from synapse.db import read_schema
from synapse.api.room_events import MessageEvent
from synapse.util.http import HttpServer

# python imports
from mock import patch, Mock
import json
import os
import sqlite3


class MessageTestCase(unittest.TestCase):
    """ Checks that messages can be PUT/GET. """

    def _setup_db(self, db_name):
        # FIXME: This is basically a copy of synapse.app.homeserver's setup
        # routine. It would be nice if we could reuse that.
        Registry.DBPOOL = adbapi.ConnectionPool(
            'sqlite3', db_name, check_same_thread=False,
            cp_min=1, cp_max=1)

        schemas = [
            "im"
        ]

        for sql_loc in schemas:
            sql_script = read_schema(sql_loc)

            with sqlite3.connect(db_name) as db_conn:
                c = db_conn.cursor()
                c.executescript(sql_script)
                c.close()
                db_conn.commit()

    def setUp(self):
        self._setup_db("_temp.db")
        self.mock_server = MockHttpServer()
        self.message_event = MessageEvent()
        self.message_event.register(self.mock_server)

    def tearDown(self):
        try:
            os.remove("_temp.db")
        except:
            pass

    @defer.inlineCallbacks
    def test_messages_in_room(self):
        # missing keys or invalid json
        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid1", '{}')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid1", '{"name":"bob"}')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid1", '{"nao')
        self.assertEquals(400, code)

        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid1", 'text only')
        self.assertEquals(400, code)

        # custom message types
        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid1",
                           '{"body":"test","msgtype":"test.custom.text"}')
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET",
                           "/rooms/rid1/messages/sid1/mid1", None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads('{"body":"test","msgtype":' +
                          '"test.custom.text"}'), response)

        # sy.text message type
        (code, response) = yield self.mock_server.trigger("PUT",
                           "/rooms/rid1/messages/sid1/mid2",
                           '{"body":"test2","msgtype":"sy.text"}')
        self.assertEquals(200, code)

        (code, response) = yield self.mock_server.trigger("GET",
                           "/rooms/rid1/messages/sid1/mid2", None)
        self.assertEquals(200, code)
        self.assertEquals(json.loads('{"body":"test2","msgtype":' +
                          '"sy.text"}'), response)


class MockHttpServer(HttpServer):

    callbacks = []  # 3-tuple of method/pattern/function

    @patch('twisted.web.http.Request')
    @defer.inlineCallbacks
    def trigger(self, http_method, path, content, mock_request):
        """ Fire an HTTP event.

        Args:
            http_method : The HTTP method
            path : The HTTP path
            content : The HTTP body
            mock_request : Mocked request to pass to the event so it can get
                           content.
        Returns:
            A tuple of (code, response) or None if no registered events were
            found.
        """

        # annoyingly we return a twisted http request which has chained calls
        # to get at the http content, hence mock it here.
        mock_content = Mock()
        config = {'read.return_value': content}
        mock_content.configure_mock(**config)
        mock_request.content = mock_content

        for (method, pattern, func) in self.callbacks:
            if http_method != method:
                continue

            matcher = pattern.match(path)
            if matcher:
                (code, response) = yield func(mock_request, *matcher.groups())
                defer.returnValue((code, response))
        defer.returnValue(None)

    def register_path(self, method, path_pattern, callback):
        self.callbacks.append((method, path_pattern, callback))