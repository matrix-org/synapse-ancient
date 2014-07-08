# -*- coding: utf-8 -*-
""" Contains base components for constructing events. """

import json


class EventFactory(object):

    """ A factory for creating events.
    """

    events = []

    def __init__(self):
        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.
        import room_events
        self.events.append(room_events.RoomTopicEvent())
        self.events.append(room_events.RoomMemberEvent())
        self.events.append(room_events.MessageEvent())

        import event_stream
        self.events.append(event_stream.EventStream())

        import register_events
        self.events.append(register_events.RegisterEvent())

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

    # TODO This feels wrong, there is no concept of an instance of a base event
    # so having this as an instance method doesn't feel right. Likewise for
    # on_PUT and on_GET: should these be @classmethod instead? Do we even *want*
    # a single event instance per request, or can we work with it being purely
    # functional?
    def register(self, http_server):
        """ Register a method, path and callback with the HTTP server. """
        pass

    @staticmethod
    def get_valid_json(content, required_keys_values):
        """ Utility method to check if the content contains the required keys
        and return the content as JSON.

        Args:
            content : The raw HTTP content
            required_keys_values : A list of tuples containing the required
                                   top-level JSON key and a python type.
        Returns:
            The content as JSON.
        Raises:
            InvalidHttpRequestError if there is a problem with the JSON.
        """
        content_json = json.loads(content)
        for (key, typ) in required_keys_values:
            if key not in content_json:
                raise InvalidHttpRequestError(
                    400,
                    BaseEvent.error("Missing %s key" % key))
            # TODO This is a little brittle at the moment since we can only
            # inspect top level keys and can't assert values. It would be nice
            # to have some kind of template which can be checked rather than a
            # list of tuples, e.g:
            # {
            #   foo : ["string","string"],
            #   bar : { "colour" : "red|green|blue" }
            # }
            # allow_extra_top_level_keys : True
            if type(content_json[key]) != typ:
                raise InvalidHttpRequestError(
                    400,
                    BaseEvent.error("Key %s is of the wrong type." % key))

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

    """ A mixin with the ability to handle PUTs. """

    def register(self, http_server):
        super(PutEventMixin, self).register(http_server)
        http_server.register_path("PUT", self.__class__.get_pattern(),
                                  self.on_PUT)

    def on_PUT(self, request, *url_args):
        raise NotImplementedError("on_PUT callback not implemented")


class GetEventMixin(object):

    """ A mixin with the ability to handle GETs. """

    def register(self, http_server):
        super(GetEventMixin, self).register(http_server)
        http_server.register_path("GET", self.__class__.get_pattern(),
                                  self.on_GET)

    def on_GET(self, request, *url_args):
        raise NotImplementedError("on_GET callback not implemented")


class PostEventMixin(object):

    """ A mixin with the ability to handle POSTs. """

    def register(self, http_server):
        super(PostEventMixin, self).register(http_server)
        http_server.register_path("POST", self.__class__.get_pattern(),
                                  self.on_POST)

    def on_POST(self, request, *url_args):
        raise NotImplementedError("on_POST callback not implemented")


class EventStreamMixin(object):

    """ A mixin with the ability to be used in the event stream.

    REST events need to undergo some standard transformations to be
    represented as events in an event stream, such as moving URL args and
    specifying a type. This mixin provides these operations, provided all the
    required data is specified.
     """
    _ev_pattern = None

    def get_event_type(self):
        """ Specify the namespaced event type.

        Returns:
            A string representing the event type, e.g. sy.room.message
        """
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
            # group pos starts at 1, and *url_args are actually a tuple,
            # hence needing to index again to the first element
            event[group_name] = url_args[0][group_pos - 1]
        return event


class InvalidHttpRequestError(Exception):
    """ Raised when an invalid request was submitted from the client.

    This class provides the ability to get a suitable return HTTP status
    code and body to send back to the client.
    """

    def __init__(self, code, body):
        super(InvalidHttpRequestError, self).__init__()
        self.http_code = code
        self.http_body = body

    def get_status_code(self):
        """ Returns a suitable HTTP status code for this exception. """
        return self.http_code

    def get_response_body(self):
        """ Returns a suitable HTTP response body for this exception. """
        return self.http_body
