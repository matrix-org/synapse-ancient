# -*- coding: utf-8 -*-

from twisted.internet import defer, reactor


def sleep(seconds):
    d = defer.Deferred()
    reactor.callLater(seconds, d.callback, seconds)
    return d
