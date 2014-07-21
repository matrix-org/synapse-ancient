# -*- coding: utf-8 -*-

# This file provides some classes for setting up (partially-populated)
# homeservers; either as a full homeserver as a real application, or a small
# partial one for unit test mocking.

# Imports required for the default HomeServer() implementation
from synapse.persistence import PersistenceService
from synapse.federation import initialize_http_federation
from synapse.api.storage import DataStore
from synapse.api.events.factory import EventFactory
from synapse.api.auth import (Auth, AccessTokenModule,
                             JoinedRoomModule, MembershipChangeModule)
from synapse.api.handlers.factory import EventHandlerFactory
from synapse.rest.base import RestServletFactory


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
            'db_pool',
            'persistence_service',
            'federation',
            'event_data_store',
            'event_factory',
            'event_handler_factory',
            'auth',
            'rest_servlet_factory',
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
    """A homeserver object that will construct most of its dependencies as
    required.

    It still requires the following to be specified by the caller:
        http_server
        http_client
        db_pool
    """

    def build_persistence_service(self):
        return PersistenceService(self)

    def build_federation(self):
        return initialize_http_federation(self)

    def build_event_data_store(self):
        return DataStore(self)

    def build_event_factory(self):
        return EventFactory()

    def build_event_handler_factory(self):
        return EventHandlerFactory(self)

    def build_auth(self):
        # TODO(paul): Likely the Auth() constructor just wants to take a
        # HomeServer instance perhaps
        event_data_store = self.get_event_data_store()
        return Auth(
            AccessTokenModule(event_data_store),
            JoinedRoomModule(event_data_store),
            MembershipChangeModule(event_data_store)
            )

    def build_rest_servlet_factory(self):
        return RestServletFactory(self)
