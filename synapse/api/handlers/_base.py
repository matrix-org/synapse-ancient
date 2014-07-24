# -*- coding: utf-8 -*-


class BaseHandler(object):

    def __init__(self, hs):
        self.store = hs.get_datastore()
        self.event_factory = hs.get_event_factory()
        self.auth = hs.get_auth()
        self.notifier = hs.get_notifier()
        self.room_lock = hs.get_room_lock_manager()
        self.hs = hs
