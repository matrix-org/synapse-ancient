# -*- coding: utf-8 -*-

from ._base import BaseHandler


class PresenceHandler(BaseHandler):

    def __init__(self, hs):
        super(PresenceHandler, self).__init__(hs)

        distributor = hs.get_distributor()
        distributor.observe("registered_user", self.registered_user)

    def registered_user(self, user):
        self.store.create_presence(user.localpart)
