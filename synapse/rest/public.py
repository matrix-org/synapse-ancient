# -*- coding: utf-8 -*-
"""This module contains REST servlets to do with public paths: /public"""
from twisted.internet import defer

from base import RestServlet

import re


class PublicRoomListRestServlet(RestServlet):
    # TODO(markjh): Namespace the client URI paths
    PATTERN = re.compile("^/public/rooms$")

    @defer.inlineCallbacks
    def on_GET(self, request):
        handler = self.handlers.room_list_handler
        data = yield handler.get_public_room_list()
        defer.returnValue((200, data))


def register_servlets(hs, http_server):
    PublicRoomListRestServlet(hs).register(http_server)
