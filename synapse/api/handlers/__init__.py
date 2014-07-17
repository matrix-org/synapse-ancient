# -*- coding: utf-8 -*-


class BaseHandler(object):

    def __init__(self, store=None, ev_factory=None, notifier=None, auth=None):
        self.store = store
        self.event_factory = ev_factory
        self.notifier = notifier
        self.auth = auth