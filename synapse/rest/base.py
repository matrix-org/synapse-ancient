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

        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.
        import room
        self.servlets.append(room.RoomTopicRestServlet(hs))
        self.servlets.append(room.RoomMemberRestServlet(hs))
        self.servlets.append(room.MessageRestServlet(hs))
        self.servlets.append(room.RoomCreateRestServlet(hs))

        from events import EventStreamRestServlet
        self.servlets.append(EventStreamRestServlet(hs))

        import register
        self.servlets.append(register.RegisterRestServlet(hs))

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

    def __init__(self, hs):
        self.hs = hs

        self.handler_factory = hs.get_event_handler_factory()
        self.event_factory = hs.get_event_factory()
        self.auth = hs.get_auth()

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
