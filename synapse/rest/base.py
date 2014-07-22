# -*- coding: utf-8 -*-
""" This module contains base REST classes for constructing REST servlets. """
from synapse.api.errors import cs_error, CodeMessageException


class RestServletFactory(object):

    """ A factory for creating REST servlets.

    These REST servlets represent the entire client-server REST API. Generally
    speaking, they serve as wrappers around events and the handlers that process
    them.

    See synapse.api.events for information on synapse events.
    """

    def __init__(self, hs):
        self.servlets = []

        handler_fac = hs.get_event_handler_factory()
        event_fac = hs.get_event_factory()
        auth = hs.get_auth()

        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.
        import room
        self.servlets.append(room.RoomTopicRestServlet(handler_fac,
                                                   event_fac, auth))
        self.servlets.append(room.RoomMemberRestServlet(handler_fac,
                                                    event_fac, auth))
        self.servlets.append(room.MessageRestServlet(handler_fac,
                                                 event_fac, auth))
        self.servlets.append(room.RoomCreateRestServlet(handler_fac,
                                                    event_fac, auth))

        from events import EventStreamRestServlet
        self.servlets.append(EventStreamRestServlet(handler_fac,
                                                event_fac, auth))

        import register
        self.servlets.append(register.RegisterRestServlet(handler_fac,
                                                      event_fac, auth))

    def register_servlets(self, http_server):
        """ Registers all REST servlets with an HTTP server.

        Args:
            http_server : The server that servlets can register paths to.
        """
        for servlet in self.servlets:
            servlet.register(http_server)


class RestServlet(object):

    """ A Synapse REST Servlet.
    """

    def __init__(self, handler_factory, event_factory, auth):
        self.handler_factory = handler_factory
        self.event_factory = event_factory
        self.auth = auth

    def register(self, http_server):
        """ Register this servlet with the given HTTP server. """
        raise NotImplementedError("RestServlet must register something.")


class InvalidHttpRequestError(CodeMessageException):
    """ Raised when an invalid request was submitted from the client.

    This class provides the ability to get a suitable return HTTP status
    code and body to send back to the client.
    """

    def __init__(self, code, body, json_wrap=True):
        super(InvalidHttpRequestError, self).__init__(code, body)
        if json_wrap:
            self.http_body = cs_error(body, code)
        else:
            self.http_body = body

    def get_status_code(self):
        """ Returns a suitable HTTP status code for this exception. """
        return self.code

    def get_response_body(self):
        """ Returns a suitable HTTP response body for this exception. """
        return self.http_body
