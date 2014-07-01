from twisted.web import server

import logging
import json


# Respond to the given HTTP request with a status code and JSON body
def send_json_response(request, code, content):
    """ Sends a JSON response to a request.

    Args:
        request : The request made.
        code : The HTTP response code
        content: A dict which contains the JSON to respond with.
    Returns:
        server.NOT_DONE_YET
    """ 
    request.setResponseCode(code)
    request.setHeader("Content-Type", "application/json")
    request.write('%s\n' % json.dumps(content))
    request.finish()
    return server.NOT_DONE_YET


def error_json(msg):
    return { "error" : msg }

# Used to indicate a particular request resulted in a fatal error
def send_500(request, e):
    """ Responds to the request with an error.

    Args:
        request : The request which has failed.
        e : The exception thrown.
    Returns:
        server.NOT_DONE_YET.
    """
    logging.exception(e)
    return send_json_response(
        request,
        500,
        error_json("Internal server error")
    )
