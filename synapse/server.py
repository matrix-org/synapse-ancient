# -*- coding: utf-8 -*-

# This file provides some classes for setting up (partially-populated)
# homeservers; either as a full homeserver as a real application, or a small
# partial one for unit test mocking.

# Imports required for the default HomeServer() implementation
from synapse.util.http import TwistedHttpServer, TwistedHttpClient
from synapse.persistence import PersistenceService
from synapse.federation import initialize_http_federation

from synapse.util import DbPool


class BaseHomeServer(object):
    """A basic homeserver object without lazy component builders.

    This will need all of the components it requires to either be passed as
    constructor arguments, or the relevant methods overriding to create them.
    Typically this would only be used for unit tests.

    For every dependency in the DEPENDENCIES list below, this class creates one
    method,
        def get_DEPENDENCY(self)
    which returns the value of that dependency. If no value has yet been set
    nor was provided to the constructor, it will attempt to call a lazy builder
    method called
        def build_DEPENDENCY(self)
    which must be implemented by the subclass. This code may call any of the
    required "get" methods on the instance to obtain the sub-dependencies that
    one requires.
    """

    DEPENDENCIES = [
            'http_server',
            'http_client',
            'persistence_service',
            'federation',
            ]

    def __init__(self, hostname, **kwargs):
        """
        Args:
            hostname : The hostname for the server.
        """
        self.hostname = hostname

        # Other kwargs are explicit dependencies
        for depname in kwargs:
            setattr(self, depname, kwargs[depname])

    @classmethod
    def _make_dependency_method(cls, depname):
        def _get(self):
            if hasattr(self, depname):
                return getattr(self, depname)

            # TODO: prevent cyclic dependencies from deadlocking
            if hasattr(self, "build_%s" % (depname)):
                builder = getattr(self, "build_%s" % (depname))
                dep = builder()
                setattr(self, depname, dep)
                return dep

            raise NotImplementedError(
                    "HomeServer has no %s nor a builder for it" % (depname)
            )

        setattr(BaseHomeServer, "get_%s" % (depname), _get)

# Build magic accessors for every dependency
for depname in BaseHomeServer.DEPENDENCIES:
    BaseHomeServer._make_dependency_method(depname)


class HomeServer(BaseHomeServer):
    """A homeserver object that will construct its dependencies as required."""

    def build_http_server(self):
        return TwistedHttpServer()

    def build_http_client(self):
        return TwistedHttpClient()

    def build_persistence_service(self):
        return PersistenceService(DbPool.get())

    def build_federation(self):
        return initialize_http_federation(self)
