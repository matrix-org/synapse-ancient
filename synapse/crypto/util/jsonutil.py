# -*- coding: utf-8 -*-

from twisted.web.server import NOT_DONE_YET
import json


def respond_with_json_object(request, code, json_object):
    """Sends a JSON object in response to the given request.

    Args:
        request (twisted.web.http.Request): The http request to respond to.
        code (int): The HTTP response code.
        json_object (dict): The json object to use as the response body.

    Returns:
        twisted.web.server.NOT_DONE_YET"""

    json_bytes = encode_canonical_json(json_object)
    return respond_with_json_bytes(request, code, json_bytes)


def respond_with_json_bytes(request, code, json_bytes):
    """Sends encoded JSON in response to the given request.

    Args:
        request (twisted.web.http.Request): The http request to respond to.
        code (int): The HTTP response code.
        json_bytes (bytes): The json bytes to use as the response body.

    Returns:
        twisted.web.server.NOT_DONE_YET"""

    request.setResponseCode(code)
    request.setHeader(b"Content-Type", b"application/json")
    request.write(json_bytes)
    request.finish()
    return NOT_DONE_YET


def encode_canonical_json(json_object):
    """Encodes the shortest UTF-8 JSON encoding with dictionary keys
    lexicographically sorted by unicode code point.

    Args:
        json_object (dict): The JSON object to encode.

    Returns:
        bytes encoding the JSON object"""

    return json.dumps(
        json_object,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True
    ).encode("UTF-8")