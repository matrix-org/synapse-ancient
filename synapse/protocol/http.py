from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web import server, resource
from twisted.internet import defer, reactor

from collections import namedtuple

import logging
import json
import urllib


logger = logging.getLogger("synapse.protocol.http")


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


class HttpClient(object):
    """ Interface for talking json over http
    """

    def put_json(self, destination, path, data):
        """ Sends the specifed json data using PUT

        Args:
            destination (str): The remote server to send the HTTP request
                to.
            path (str): The HTTP path.
            data (dict): A dict containing the data that will be used as
                the request body. This will be encoded as JSON.

        Returns:
            Deferred: Succeeds when we get *any* HTTP response.

            The result of the deferred is a tuple of `(code, response)`,
            where `response` is a dict representing the decoded JSON body.
        """
        pass

    def get_json(self, destination, path, args=None):
        """ Get's some json from the given host homeserver and path

        Args:
            destination (str): The remote server to send the HTTP request
                to.
            path (str): The HTTP path.
            args (dict): A dictionary used to create query strings, defaults to
                None.
                **Note**: The value of each key is assumed to be an iterable
                and *not* a string.

        Returns:
            Deferred: Succeeds when we get *any* HTTP response.

            The result of the deferred is a tuple of `(code, response)`,
            where `response` is a dict representing the decoded JSON body.
        """
        pass


# Respond to the given HTTP request with a status code and
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

    request.setHeader("Content-Type", "application/json")

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
            # Loop through all the registered callback to check if the method
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


class TwistedHttpClient(HttpClient):
    """ Wrapper around the twisted HTTP client api.

    Attributes:
        agent (twisted.web.client.Agent): The twisted Agent used to send the
            requests.
    """

    def __init__(self):
        self.agent = Agent(reactor)

    @defer.inlineCallbacks
    def put_json(self, destination, path, data):
        response = yield self._create_put_request(
                "http://%s%s" % (destination, path),
                data,
                headers_dict={"Content-Type": ["application/json"]}
            )

        logger.debug("Getting resp body")
        body = yield readBody(response)
        logger.debug("Got resp body")

        defer.returnValue((response.code, body))

    @defer.inlineCallbacks
    def get_json(self, destination, path, args=None):
        if args:
            # generates a list of strings of form "k=v".
            # First we generate a list of lists, and then flatten it using
            # the "fun" list comprehension syntax.
            qs = [
                i for s in
                [
                    ["%s=%s" % (k, urllib.quote_plus(w)) for w in v]
                    for k, v in args.items()
                ]
                for i in s
            ]
            path = "%s?%s" % (path, "&".join(qs))

        response = yield self._create_get_request(
                "http://%s%s" % (destination, path)
            )

        body = yield readBody(response)

        defer.returnValue(json.loads(body))

    def _create_put_request(self, url, json_data, headers_dict={}):
        """ Wrapper of _create_request to issue a PUT request
        """

        if "Content-Type" not in headers_dict:
            raise defer.error(
                RuntimeError("Must include Content-Type header for PUTs"))

        return self._create_request(
            "PUT",
            url,
            producer=_JsonProducer(json_data),
            headers_dict=headers_dict
        )

    def _create_get_request(self, url, headers_dict={}):
        """ Wrapper of _create_request to issue a GET request
        """
        return self._create_request(
            "GET",
            url,
            headers_dict=headers_dict
        )

    @defer.inlineCallbacks
    def _create_request(self, method, url, producer=None, headers_dict={}):
        """ Creates and sends a request to the given url
        """
        headers_dict["User-Agent"] = ["Synapse"]

        logger.debug("Sending request: %s %s", method, url)

        try:
            response = yield self.agent.request(
                    method,
                    url.encode("UTF8"),
                    Headers(headers_dict),
                    producer
                )

            logger.debug("Got response to %s" % method)
        except Exception as e:
            logger.error("Got error in _create_request")
            _print_ex(e)

            raise

        if 200 <= response.code < 300:
            # We need to update the transactions table to say it was sent?
            pass
        else:
            # :'(
            # Update transactions table?
            logger.error(
                "Got response %d %s", response.code, response.phrase
            )
            raise RuntimeError("Got response %d %s"
                    % (response.code, response.phrase))

        defer.returnValue(response)


def _print_ex(e):
    if hasattr(e, "reasons") and e.reasons:
        for ex in e.reasons:
            _print_ex(ex)
    else:
        logger.exception(e)


class _JsonProducer(object):
    """ Used by the twisted http client to create the HTTP body from json
    """
    def __init__(self, jsn):
        self.body = json.dumps(jsn).encode("utf8")
        self.length = len(self.body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return defer.succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
