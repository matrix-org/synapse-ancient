# -*- coding: utf-8 -*-
from twisted.internet import defer

from ._base import SQLBaseStore


class ProfileStore(SQLBaseStore):

    def get_profile_displayname(self, user_localpart):
        return defer.succeed("Frank")
