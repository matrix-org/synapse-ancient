from twisted.web import server, resource
from twisted.internet import reactor, defer

import synapse.util.http_utils as http_utils

import argparse
import json
import sys

class SynapseResource(resource.Resource):
    """ The root resource '/'. Sets up child resources. """

    def __init__(self, synapse_api):
        """ Construct a synapse resource.

        Args:
            synapse_api : The SynapseApi to invoke on incoming requests.
        """
        resource.Resource.__init__(self)
        self.putChild("events", EventsResource(synapse_api))

    def render_GET(self, request):
        print "HTTP %s\nURI: %s" % (request.method, request.uri)
        return "This is not the page you are looking for."


class EventsResource(resource.Resource):
    """ The events resource /events """
    isLeaf = True

    def __init__(self, synapse_api):
        resource.Resource.__init__(self)
        self.synapi = synapse_api

    def render_GET(self, request):
        print "GET %s : %s" % (request.path, request.args)

        # Check the request is valid
        if request.path != "/events":
            return http_utils.send_json_response(request, 400, http_utils.error_json("Can only GET on /events"))
        if "baseVer" not in request.args:
            return http_utils.send_json_response(request, 400, http_utils.error_json("Missing baseVer"))

        ver = request.args["baseVer"][0]
        self._async_process_event_get(request, ver).addErrback(self._request_fail, request)
        return server.NOT_DONE_YET

    def render_PUT(self, request):
        content = request.content.read()
        print "PUT %s : %s" % (request.path, content)

        # Check the request is valid
        if request.path.count("/") != 2:
            return http_utils.send_json_response(request, 400, http_utils.error_json("Path must be of the form /events/$event_id"))

        event_id = request.path.split("/")[-1]
        try:
            content = json.loads(content)
        except:
            return http_utils.send_json_response(request, 400, http_utils.error_json("Body must be JSON."))

        self._async_process_event_put(request, event_id, content).addErrback(self._request_fail, request)
        return server.NOT_DONE_YET

    def _request_fail(self, err, request):
        http_utils.send_500(request, err)

    @defer.inlineCallbacks
    def _async_process_event_put(self, request, event_id, content):
        (code, json) = yield self.synapi.process_event_put(request, event_id, content)
        http_utils.send_json_response(request, code, json)

    @defer.inlineCallbacks
    def _async_process_event_get(self, request, version):
        (code, json) = yield self.synapi.process_event_get(request, version)
        http_utils.send_json_response(request, code, json)

