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

    @classmethod
    def get_pattern(cls):
        """ Get the regex path pattern to match. This should be defined by
        subclasses.

        Returns:
            A regex compiled pattern.
        """
        raise NotImplementedError("Event must specify a URL pattern.")

    def register(self, http_server):
        """ Register a method, path and callback with the HTTP server. """
        pass

    @staticmethod
    def get_valid_json(content, required_keys):
        """ Utility method to check if the content contains the required keys
        and return the content as JSON.

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
        """ Utility method for constructing an error response.

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
        http_server.register_path("PUT", self.__class__.get_pattern(),
                                  self.on_PUT)

    def on_PUT(self, request, groups):
        raise NotImplementedError("on_PUT callback not implemented")


class GetEventMixin(object):

    """ A BaseEvent mixed with the ability to handle GETs. """

    def register(self, http_server):
        super(GetEventMixin, self).register(http_server)
        http_server.register_path("GET", self.__class__.get_pattern(),
                                  self.on_GET)

    def on_GET(self, request, groups):
        raise NotImplementedError("on_GET callback not implemented")


class EventStreamMixin(object):

    """ A BaseEvent mixed with the ability to be used in the event stream.

    REST events need to undergo some standard transformations to be
    represented as events in an event stream, such as moving URL args and
    specifying a type. This mixin provides these operations, provided all the
    required data is specified.
     """
    _ev_pattern = None

    def get_event_type(self):
        """ Specify the namespaced event type. """
        raise NotImplementedError()

    def get_event_stream_dict(self, *url_args, **kwargs):
        """ Constructs a dict which can be streamed as event JSON.

        Args:
            url_args : The matched groups from the URL.
            kwargs : Additional keys to add to the event dict.
        Returns:
            An event streamble dict.
        Raises:
            KeyError if there are unnamed matched groups, as the names are used
            as the keys for the dict.
        """
        event = {}
        # set additional keys first so we clobber correctly.
        for key, value in kwargs.iteritems():
            event[key] = value

        event["type"] = self.get_event_type()

        # set url args based on the group name and complain if there is no name
        if not self._ev_pattern:
            self._ev_pattern = self.__class__.get_pattern()
            if len(self._ev_pattern.groupindex) != self._ev_pattern.groups:
                raise KeyError("Event pattern has unnamed groups.")

        # the url_args in http_server match up to the pattern for the url, so
        # we can just index into url_args and use the group name from the
        # pattern. Ideally, http_server would return the raw SRE_Pattern which
        # would preserve group names, but we don't currently.
        for group_name, group_pos in self._ev_pattern.groupindex.iteritems():
            # group pos starts at 1, and *url_args are actually a group tuple,
            # hence needing to index again to the first element
            event[group_name] = url_args[group_pos - 1][0]
        return event


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)$")

    def get_event_type(self):
        return "sy.room.topic"

    def on_GET(self, request, *url_args):
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"rooms": "None"})

    def on_PUT(self, request, *url_args):
        try:
            print BaseEvent.get_valid_json(request.content.read(), ["name"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"room": "topic"})
