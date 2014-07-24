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
        http_server = hs.get_http_server()

        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.

        import room
        room.register_servlets(hs, http_server)

        import events
        events.register_servlets(hs, http_server)

        import register
        register.register_servlets(hs, http_server)

        import profile
        profile.register_servlets(hs, http_server)


class RestServlet(object):

    """ A Synapse REST Servlet.

    An implementing class can either provide its own custom 'register' method,
    or use the automatic pattern handling provided by the base class.

    To use this latter, the implementing class instead provides a `PATTERN`
    class attribute containing a pre-compiled regular expression. The automatic
    register method will then use this method to register any of the following
    instance methods associated with the corresponding HTTP method:

      on_GET
      on_PUT
      on_POST
      on_DELETE
      on_OPTIONS
    """

    def __init__(self, hs):
        self.hs = hs

        self.handlers = hs.get_handlers()
        self.event_factory = hs.get_event_factory()
        self.auth = hs.get_auth()

    def register(self, http_server):
        """ Register this servlet with the given HTTP server. """
        if hasattr(self, "PATTERN"):
            pattern = self.PATTERN

            for method in ("GET", "PUT", "POST", "OPTIONS", "DELETE"):
                if hasattr(self, "on_%s" % (method)):
                    http_server.register_path(method, pattern,
                            getattr(self, "on_%s" % (method)))
        else:
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
