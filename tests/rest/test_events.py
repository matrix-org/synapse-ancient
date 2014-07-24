# -*- coding: utf-8 -*-
""" Tests REST events for /events paths."""
from twisted.trial import unittest


class EventStreamPaginationApiTestCase(unittest.TestCase):
    """ Tests event streaming query parameters and start/end keys used in the
    Pagination stream API. """
    user_id = "sid1"

    def setUp(self):
        # configure stream and inject items
        pass

    def tearDown(self):
        pass

    def test_long_poll(self):
        # stream from 'end' key, send (self+other) message, expect message.

        # stream from 'END', send (self+other) message, expect message.

        # stream from 'end' key, send (self+other) topic, expect topic.

        # stream from 'END', send (self+other) topic, expect topic.

        # stream from 'end' key, send (self+other) invite, expect invite.

        # stream from 'END', send (self+other) invite, expect invite.

        pass

    def test_stream_forward(self):
        # stream from START, expect injected items

        # stream from 'start' key, expect same content

        # stream from 'end' key, expect nothing

        # stream from 'END', expect nothing

        # The following is needed for cases where content is removed e.g. you
        # left a room, so the token you're streaming from is > the one that
        # would be returned naturally from START>END.
        # stream from very new token (higher than end key), expect same token
        # returned as end key
        pass

    def test_limits(self):
        # stream from a key, expect limit_num items

        # stream from START, expect limit_num items

        pass

    def test_range(self):
        # stream from key to key, expect X items

        # stream from key to END, expect X items

        # stream from START to key, expect X items

        # stream from START to END, expect all items
        pass

    def test_direction(self):
        # stream from END to START and fwds, expect newest first

        # stream from END to START and bwds, expect oldest first

        # stream from START to END and fwds, expect oldest first

        # stream from START to END and bwds, expect newest first

        pass


class EventStreamTestCase(unittest.TestCase):
    """ Tests event streaming (GET /events). """
    user_id = "sid1"

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_stream_perms(self):
        # invalid token, expect 403

        # valid token, expect content

        # invited to room (expect no content for room)

        # joined room (expect all content for room)

        # left to room (expect no content for room)
        pass

    def test_stream_items(self):
        # new user, no content

        # join room, expect 1 item (join)

        # send message, expect 2 items (join,send)

        # set topic, expect 3 items (join,send,topic)

        # someone else join room, expect 4 (join,send,topic,join)

        # someone else send message, expect 5 (join,send.topic,join,send)

        # someone else set topic, expect 6 (join,send,topic,join,send,topic)
        pass