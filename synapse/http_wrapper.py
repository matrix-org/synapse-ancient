from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web import server, resource
from twisted.internet import defer, reactor

from collections import namedtuple

import logging
import json


class HttpServer(object):
    """ Interface for registering callbacks on a HTTP server
    """

    def register_path(self, method, path_pattern, callback):
        """ Register a callback that gefrot's fired if we receive a http request
            with the given method for a path that matches the given regex. If
            the regex contains groups these get's passed to the calback via
            an unpacked tuple.
        """
        pass


class HttpClient(object):
    """ Interface for talking json over http
    """

    def put_json(self, destination, path, data):
        """ Sends the specifed json data using PUT

            Returns a defered with tuple of (response_code, response_json_body)
        """
        pass

    def get_json(self, destination, path):
        """ Get's some json from the given host homeserver and path

            Returns a defered with tuple of (response_code, response_json_body)
        """
        pass


# Respond to the given HTTP request with a status code and
def send_response(request, code, content):
    request.setResponseCode(code)
    request.setHeader("Content-Type", "application/json")

    request.write('%s\n' % json.dumps(content))
    request.finish()
    return server.NOT_DONE_YET


# Used to indicate a particular request resulted in a fatal error
def handle_err(request, e):
    logging.exception(e)
    return send_response(
        request,
        500,
        {"error": "Internal server error"}
    )

_HttpClientPathEntry = namedtuple(
        "_HttpClientPathEntry",
        ["pattern", "callback"]
    )


# The actual HTTP server impl, using twisted http server
class TwsitedHttpServer(HttpServer, resource.Resource):
    """ This wraps the twisted HTTP server, and triggers the
        correct callbacks on the transport_layer.

        Register callbacks via register_path()
    """

    isLeaf = True

    def __init__(self):
        resource.Resource.__init__(self)

        self.path_regexs = {}

    def register_path(self, method, path_pattern, callback):
        """ Register a callback that gefrot's fired if we receive a http request
            with the given method for a path that matches the given regex. If
            the regex contains groups these get's passed to the calback via
            an unpacked tuple.
        """
        self.path_regexs.setdefault(method, []).append(
                _HttpClientPathEntry(path_pattern, callback)
            )

    def start_listening(self, port):
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
            for path_entry in self.path_regexs.get(request.method, []):
                m = path_entry.pattern.match(request.path)
                if m:
                    code, response = yield path_entry.callback(
                            request,
                            *m.groups()
                        )

                    send_response(request, code, response)
                    return

            # Huh. No one wanted to handle that? Fiiiiiine. Send 400.
            send_response(
                    request,
                    400,
                    {"error": "Unrecognized request"}
                )
        except Exception as e:
            # Awww, what?!
            # FIXME: Insert logging.
            handle_err(request, e)


class TwistedHttpClient(HttpClient):
    """ Convenience wrapper around the twisted HTTP client api.
    """

    def __init__(self):
        self.agent = Agent(reactor)

    @defer.inlineCallbacks
    def put_json(self, destination, path, data):
        """ Sends the specifed json data using PUT
        """
        response = yield self._create_put_request(
                "http://%s%s" % (destination, path),
                data,
                headers_dict={"Content-Type": ["application/json"]}
            )

        body = yield readBody(response)

        defer.returnValue((response.code, body))

    @defer.inlineCallbacks
    def get_json(self, destination, path):
        """ Get's some json from the given host homeserver and path
        """
        response = yield self._create_get_request(
                "http://%s%s" % (destination, path)
            )

        body = yield readBody(response)

        defer.returnValue(json.loads(body))

    def _create_put_request(self, url, json_data, headers_dict={}):
        """ Wrapper of _create_request to issue a PUT request
        """

        if "Content-Type" not in headers_dict:
            raise RuntimeError("Must include Content-Type header for PUTs")

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

        logging.debug("Sending request: %s %s", method, url)

        try:
            response = yield self.agent.request(
                    method,
                    url.encode("UTF8"),
                    Headers(headers_dict),
                    producer
                )
        except Exception as e:
            _print_ex(e)

            return

        if 200 <= response.code < 300:
            # We need to update the transactions table to say it was sent?
            pass
        else:
            # :'(
            # Update transactions table?
            logging.error(
                "Got response %d %s", response.code, response.phrase
            )
            raise RuntimeError("Got response %d %s"
                    % (response.code, response.phrase))

        defer.returnValue(response)


def _print_ex(e):
    if hasattr(e, "reasons"):
        for ex in e.reasons:
            _print_ex(ex)
    else:
        logging.exception(e)


# Used by the twisted http client to create the HTTP
# body from json
class _JsonProducer(object):
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