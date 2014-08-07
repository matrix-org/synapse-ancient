# -*- coding: utf-8 -*

from twisted.internet import defer

from synapse.types import RoomName
from base import RestServlet, InvalidHttpRequestError


class DirectoryServer(RestServlet):
    PATTERN = re.compile("^/ds/room/(?P<room_name>[^/]*)$")

    def on_GET(self, request, room_name):
        # TODO(erikj): Handle request
        pass

    def on_PUT(self, request, room_name):
        # TODO(erikj): Exceptions
        content = json.loads(request.content.read())

        room_name_obj = RoomName.from_string(room_name, self.hs)

        room_id = content["room_id"]
        servers = content["servers"]

        # TODO(erikj): Check types.

        # TODO(erikj): Handle request
