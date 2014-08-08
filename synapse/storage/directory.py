# -*- coding: utf-8 -*-
from ._base import SQLBaseStore


class DirectoryStore(SQLBaseStore):

    def get_association_from_room_name(self, room_name_str):
        """ Get's the room_id and server list for a given room_name

        Returns:
            namedtuple: with keys "room_id" and "servers" or None if
            no association can be found
        """
        raise NotImplementedError("get_association_from_room_name")

    def create_room_name_association(self, room_name, room_id, servers):
        # TODO(erikj): Should this throw if room_name is already in use?
        raise NotImplementedError("create_room_name_association")
