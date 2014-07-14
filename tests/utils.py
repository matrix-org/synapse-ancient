from synapse.util.http import HttpServer

from twisted.internet import defer

from mock import patch, Mock
import urlparse


class MockHttpServer(HttpServer):

    def __init__(self):
        self.callbacks = []  # 3-tuple of method/pattern/function

    @patch('twisted.web.http.Request')
    @defer.inlineCallbacks
    def trigger(self, http_method, path, content, mock_request):
        """ Fire an HTTP event.

        Args:
            http_method : The HTTP method
            path : The HTTP path
            content : The HTTP body
            mock_request : Mocked request to pass to the event so it can get
                           content.
        Returns:
            A tuple of (code, response)
        Raises:
            KeyError If no event is found which will handle the path.
        """

        # annoyingly we return a twisted http request which has chained calls
        # to get at the http content, hence mock it here.
        mock_content = Mock()
        config = {'read.return_value': content}
        mock_content.configure_mock(**config)
        mock_request.content = mock_content

        # return the right path if the event requires it
        mock_request.path = path

        # add in query params to the right place
        try:
            mock_request.args = urlparse.parse_qs(path.split('?')[1])
            mock_request.path = path.split('?')[0]
        except:
            pass

        for (method, pattern, func) in self.callbacks:
            if http_method != method:
                continue

            matcher = pattern.match(path)
            if matcher:
                (code, response) = yield func(mock_request, *matcher.groups())
                defer.returnValue((code, response))
        raise KeyError("No event can handle %s" % path)

    def register_path(self, method, path_pattern, callback):
        self.callbacks.append((method, path_pattern, callback))


class MockRegisteredUserModule():
    """A mock of synapse.api.auth.RegisteredUserModule."""

    def __init__(self, user_id):
        """Register as a given user.

        Args:
            user_id - The user ID to auth as.
        """
        self.user_id = user_id

    def get_user_by_req(self, request):
        return self.user_id

    def get_user_by_token(self, token):
        return self.user_id
