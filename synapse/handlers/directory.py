# -*- coding: utf-8 -*-

from twisted.internet import defer
from ._base import BaseHandler

from synapse.api.errors import SynapseError

import logging
import json

logger = logging.getLogger(__name__)


class DirectoryHandler(BaseHandler):

    def __init__(self, hs):
        super(DirectoryHandler, self).__init__(hs)
        self.hs = hs
        self.clock = hs.get_clock()

    @defer.inlineCallbacks
    def create_association(self, room_alias, room_id, servers):
        # TODO(erikj): Do auth.

        if not room_alias.is_mine:
            raise SynapseError(400, "Room alias must be local")
            # TODO(erikj): Change this.

        # TODO(erikj): Add transactions.

        # TODO(erikj): Check if there is a current association.

        yield self.store.create_room_alias_association(
            room_alias,
            room_id,
            servers
        )

    @defer.inlineCallbacks
    def get_association(self, room_alias):
        # TODO(erikj): Do auth

        if room_alias.is_mine:
            result = yield self.store.get_association_from_room_alias(
                room_alias
            )
        else:
            # TODO(erikj): Hit out to remote HS.
            raise NotImplementedError("Can't do remote room alias fetching")

        # TODO(erikj): Handle result

        if not result:
            defer.returnValue({})
            return

        room_id = result.room_id
        servers = result.servers

        defer.returnValue({
            "room_id": room_id,
            "servers": servers,
        })
        return
