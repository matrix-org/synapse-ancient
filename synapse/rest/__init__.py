# -*- coding: utf-8 -*-

from . import (
    room, events, register, profile, public, presence, user, directory
)

class RestServletFactory(object):

    """ A factory for creating REST servlets.

    These REST servlets represent the entire client-server REST API. Generally
    speaking, they serve as wrappers around events and the handlers that
    process them.

    See synapse.api.events for information on synapse events.
    """

    def __init__(self, hs):
        http_server = hs.get_http_server()

        # TODO(erikj): There *must* be a better way of doing this.
        room.register_servlets(hs, http_server)
        events.register_servlets(hs, http_server)
        register.register_servlets(hs, http_server)
        profile.register_servlets(hs, http_server)
        public.register_servlets(hs, http_server)
        presence.register_servlets(hs, http_server)
        user.register_servlets(hs, http_server)
        directory.register_servlets(hs, http_server)


