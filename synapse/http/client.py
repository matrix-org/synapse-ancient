# -*- coding: utf-8 -*-

from twisted.internet import defer, reactor
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

import json
import logging
import urllib


logger = logging.getLogger(__name__)


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
            qs = urllib.urlencode(args, True)
            path = "%s?%s" % (path, qs)

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

        retries_left = 5

        while True:
            try:
                response = yield self.agent.request(
                    method,
                    url.encode("UTF8"),
                    Headers(headers_dict),
                    producer
                )

                logger.debug("Got response to %s" % method)
                break
            except Exception as e:
                logger.error("Got error in _create_request")
                _print_ex(e)

                if retries_left:
                    yield sleep(2 ** (5 - retries_left))
                    retries_left -= 1
                else:
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
            raise RuntimeError(
                "Got response %d %s"
                % (response.code, response.phrase)
            )

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
