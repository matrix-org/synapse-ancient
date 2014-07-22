# -*- coding: utf-8 -*-

from twisted.internet import defer

import logging


logger = logging.getLogger(__name__)


class Lock(object):

    def __init__(self, deferred):
        self._deferred = deferred
        self.released = False

    def release(self):
        self.released = True
        self._deferred.callback(None)

    def __del__(self):
        if not self.released:
            logger.critical("Lock was destructed but never released!")
            self.release()

    def __enter__(self):
            return self

    def __exit__(self, type, value, traceback):
        self.release()


class LockManager(object):
    """ Utility class that allows us to lock based on a `key` """

    def __init__(self):
        self._lock_deferreds = {}

    @defer.inlineCallbacks
    def lock(self, key):
        """ Allows us to block until it is our turn.
        Args:
            key (str)
        Returns:
            Lock
        """
        new_deferred = defer.Deferred()
        old_deferred = self._lock_deferreds.get(key)
        self._lock_deferreds[key] = new_deferred

        if old_deferred:
            yield old_deferred

        defer.returnValue(Lock(new_deferred))
