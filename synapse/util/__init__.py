# -*- coding: utf-8 -*-

from .async import sleep
from .stringutils import origin_from_ucid

from twisted.internet import reactor

import time


class Clock(object):
    """A small utility that obtains current time-of-day so that time may be
    mocked during unit-tests.

    TODO(paul): Also move the sleep() functionallity into it
    """

    def time(self):
        """Returns the current system time in seconds since epoch."""
        return time.time()

    def time_msec(self):
        """Returns the current system time in miliseconds since epoch."""
        return self.time() * 1000

    def call_later(self, delay, callback):
        return reactor.callLater(delay, callback)

    def cancel_call_later(self, timer):
        timer.cancel()
