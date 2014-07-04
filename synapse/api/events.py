import json
import re


class EventFactory(object):

    """ A factory for creating events.
    """

    events = []

    def __init__(self):
        self.events.append(RoomTopicEvent())

    def register_paths(self, http_server):
        """ Registers paths for all known events.

        Args:
            http_server : The server to register paths to.
        """
        for event in self.events:
            event.register(http_server)


class BaseEvent(object):

    """ A Synapse REST Event.
    """

    def get_pattern(self):
        """ Get the regex path pattern to match.

        Returns:
            A regex compiled pattern.
        """
        raise NotImplementedError("Event must specify a URL pattern.")

    def register(self, http_server):
        """ Register a method, path and callback with the HTTP server. """
        pass

    @staticmethod
    def get_valid_json(content, required_keys):
        """ Check if the content contains the required keys and return the
        content as JSON.

        Args:
            content : The raw HTTP content
            required_keys : A list of required top-level JSON keys.
        Returns:
            The content as JSON.
        Raises:
            KeyError if a required key is missing.
            ValueError if the content isn't JSON.
        """
        content_json = json.loads(content)
        for key in required_keys:
            if key not in content_json:
                raise KeyError("Missing %s key" % key)
        return content_json

    @staticmethod
    def error(msg, code=0, **kwargs):
        """ Construct an error response.

        Args:
            msg : The error message.
            code : The error code.
            kwargs : Additional keys to add to the response.
        Returns:
            A dict representing the error response JSON.
        """
        err = {"error": msg, "errcode": code}
        for key, value in kwargs.iteritems():
            err[key] = value
        return err


class PutEventMixin(object):

    """ A BaseEvent mixed with the ability to handle PUTs. """

    def register(self, http_server):
        super(PutEventMixin, self).register(http_server)
        http_server.register_path("PUT", self.get_pattern(), self.on_PUT)

    def on_PUT(self, request, groups):
        raise NotImplementedError("on_PUT callback not implemented")


class GetEventMixin(object):

    """ A BaseEvent mixed with the ability to handle GETs. """

    def register(self, http_server):
        super(GetEventMixin, self).register(http_server)
        http_server.register_path("GET", self.get_pattern(), self.on_GET)

    def on_GET(self, request, groups):
        raise NotImplementedError("on_GET callback not implemented")


class EventStreamMixin(object):

    """ A BaseEvent mixed with the ability to be used in the event stream.

    REST events need to undergo some standard transformations to be
    represented as events in an event stream, such as moving URL args and
    specifying a type. This mixin provides these operations, provided all the
    required data is specified.
     """

    def get_event_type(self):
        """ Specify the namespaced event type. """
        raise NotImplementedError()


class RoomTopicEvent(PutEventMixin, GetEventMixin, BaseEvent):

    def get_pattern(self):
        return re.compile("^/rooms/([^/]*)$")

    def on_PUT(self, request, groups):
        try:
            print BaseEvent.get_valid_json(request.content.read(), ["name"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"room": "topic"})
