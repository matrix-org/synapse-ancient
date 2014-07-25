# -*- coding: utf-8 -*-


from twisted.web import server, resource
from twisted.internet import defer

from collections import namedtuple

import logging
import json


logger = logging.getLogger(__name__)


class HttpServer(object):
    """ Interface for registering callbacks on a HTTP server
    """

    def register_path(self, method, path_pattern, callback):
        """ Register a callback that get's fired if we receive a http request
        with the given method for a path that matches the given regex.

        If the regex contains groups these get's passed to the calback via
        an unpacked tuple.

        Args:
            method (str): The method to listen to.
            path_pattern (str): The regex used to match requests.
            callback (function): The function to fire if we receive a matched
                request. The first argument will be the request object and
                subsequent arguments will be any matched groups from the regex.
                This should return a tuple of (code, response).
        """
        pass


# Respond to the given HTTP request with a status code and content
def _send_response(request, code, content):
    """Sends a JSON response to the given request.

    Args:
        request (twisted.web.http.Request): The http request we are responding
            to.
        code (int): The HTTP response code.
        content (dict): The content to be used json encoded and used as the
            response body.

    Returns:
        twisted.web.server.NOT_DONE_YET

    """
    request.setResponseCode(code)

    # Hack to send pretty printed json in response to requests made by
    # curl.
    ident = None
    for h in request.requestHeaders.getRawHeaders("User-Agent", default=[]):
        if "curl" in h:
            ident = 4
            break

    # XXX: really? the way to set a header on the response is to set it on the
    # request object?!
    request.setHeader("Content-Type", "application/json")

    # Hack to turn on CORS for everyone for now...
    request.setHeader("Access-Control-Allow-Origin", "*");
    request.setHeader("Access-Control-Allow-Methods",
        "GET, POST, PUT, DELETE, OPTIONS");
    request.setHeader("Access-Control-Allow-Headers",
        "Origin, X-Requested-With, Content-Type, Accept");

    request.write('%s\n' % json.dumps(content, indent=ident))
    request.finish()


# Used to indicate a particular request resulted in a fatal error
def _handle_error(request, e):
    """ Called when there was an error handling the request. Logs the exception
    and repsonds to the request with a 500 Internal Server Error

    Args:
        request (twisted.web.http.Request): The HTTP request that went wrong.
        e (Exception): The exception indicating what went wrong.
    """
    logger.exception(e)
    _send_response(
        request,
        500,
        {"error": "Internal server error"}
    )


_HttpClientPathEntry = namedtuple(
    "_HttpClientPathEntry",
    ["pattern", "callback"]
)

# The actual HTTP server impl, using twisted http server
class TwistedHttpServer(HttpServer, resource.Resource):
    """ This wraps the twisted HTTP server, and triggers the correct callbacks
    on the transport_layer.

    Register callbacks via register_path()
    """

    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)

        self.path_regexs = {}

    def register_path(self, method, path_pattern, callback):
        self.path_regexs.setdefault(method, []).append(
            _HttpClientPathEntry(path_pattern, callback)
        )

    def start_listening(self, port):
        """ Registers the http server with the twisted reactor.

        Args:
            port (int): The port to listen on.

        """
        reactor.listenTCP(port, server.Site(self))

    # Gets called by twisted
    def render(self, request):
        """ This get's called by twisted every time someone sends us a request.
        """
        self._async_render(request)
        return server.NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render(self, request):
        """ This get's called by twisted every time someone sends us a request.
            This checks if anyone has registered a callback for that method and
            path.
        """
        try:
            # Loop through all the registered callbacks to check if the method
            # and path regex match
            for path_entry in self.path_regexs.get(request.method, []):
                m = path_entry.pattern.match(request.path)
                if m:
                    # We found a match! Trigger callback and then return the
                    # returned response. We pass both the request and any
                    # matched groups from the regex to the callback.
                    code, response = yield path_entry.callback(
                        request,
                        *m.groups()
                    )

                    _send_response(request, code, response)
                    return

            # Huh. No one wanted to handle that? Fiiiiiine. Send 400.
            _send_response(
                request,
                400,
                {"error": "Unrecognized request"}
            )
        except Exception as e:
            # Awww, what?!
            # FIXME: Insert logging.
            _handle_error(request, e)