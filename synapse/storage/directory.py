# -*- coding: utf-8 -*-
from ._base import SQLBaseStore
from twisted.internet import defer

from collections import namedtuple


RoomAliasMapping = namedtuple(
    "RoomAliasMapping",
    ("room_id", "room_alias", "servers",)
)


class DirectoryStore(SQLBaseStore):

    @defer.inlineCallbacks
    def get_association_from_room_alias(self, room_alias):
        """ Get's the room_id and server list for a given room_alias

        Returns:
            namedtuple: with keys "room_id" and "servers" or None if
            no association can be found
        """
        room_id = yield self._simple_select_one_onecol(
            "room_aliases",
            {"room_alias": room_alias.to_string()},
            "room_id",
            allow_none=True,
        )

        if not room_id:
            defer.returnValue(None)
            return

        servers = yield self._simple_select_onecol(
            "room_alias_servers",
            {"room_alias": room_alias.to_string()},
            "server",
        )

        if not servers:
            defer.returnValue(None)
            return

        defer.returnValue(RoomAliasMapping(room_id, room_alias.to_string(), servers))

    @defer.inlineCallbacks
    def create_room_alias_association(self, room_alias, room_id, servers):
        yield self._simple_insert(
            "room_aliases",
            {
                "room_alias": room_alias.to_string(),
                "room_id": room_id.to_string(),
            },
        )

        for server in servers:
            # TODO(erikj): Fix this to bulk insert
            yield self._simple_insert(
                "room_alias_servers",
                {
                    "room_alias": room_alias.to_string(),
                    "server": server,
                }
            )

