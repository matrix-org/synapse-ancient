# -*- coding: utf-8 -*-
""" This module contains base event classes for constructing REST events. """
from synapse.api.errors import cs_error, CodeMessageException

import json


class RestEventFactory(object):

    """ A factory for creating REST events.

    These REST events represent the entire client-server REST API. Generally
    speaking, they serve as wrappers around synapse events.

    See synapse.api.events.base for information on synapse events.
    """

    events = []

    def __init__(self, event_factory):
        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.
        import room
        self.events.append(room.RoomTopicRestEvent(event_factory))
        self.events.append(room.RoomMemberRestEvent(event_factory))
        self.events.append(room.MessageRestEvent(event_factory))
        self.events.append(room.RoomCreateRestEvent(event_factory))

        from events import EventStreamRestEvent
        self.events.append(EventStreamRestEvent(event_factory))

        import register
        self.events.append(register.RegisterRestEvent(event_factory))

    def register_events(self, http_server):
        """ Registers all REST events with an HTTP server.

        Args:
            http_server : The server that events can register paths to.
        """
        for event in self.events:
            event.register(http_server)


class RestEvent(object):

    """ A Synapse REST Event.
    """

    def __init__(self, event_factory):
        self.event_factory = event_factory
        # cheat for now and leak the store
        self.data_store = self.event_factory.store

    def get_pattern(self):
        """ Get the regex path pattern to match. This should be defined by
        subclasses.

        Returns:
            A regex compiled pattern.
        """
        raise NotImplementedError("Event must specify a URL pattern.")

    def register(self, http_server):
        """ Register this event with the given HTTP server. """
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
        try:
            content_json = json.loads(content)
            for (key, typ) in required_keys_values:
                if key not in content_json:
                    raise InvalidHttpRequestError(400, "Missing %s key" % key)
                # TODO This is a little brittle at the moment since we can only
                # inspect top level keys and can't assert values. It would be
                # nice to have some kind of template which can be checked
                # rather than a list of tuples, e.g:
                # {
                #   foo : ["string","string"],
                #   bar : { "colour" : "red|green|blue" }
                # }
                # allow_extra_top_level_keys : True
                if type(content_json[key]) != typ:
                    raise InvalidHttpRequestError(400,
                        "Key %s is of the wrong type." % key)
        except ValueError:
            raise InvalidHttpRequestError(400, "Content must be JSON.")

        return content_json


class PutEventMixin(object):

    """ A mixin with the ability to handle PUTs. """

    def register(self, http_server):
        super(PutEventMixin, self).register(http_server)
        http_server.register_path("PUT", self.get_pattern(),
                                  self.on_PUT)

    def on_PUT(self, request, *url_args):
        raise NotImplementedError("on_PUT callback not implemented")


class GetEventMixin(object):

    """ A mixin with the ability to handle GETs. """

    def register(self, http_server):
        super(GetEventMixin, self).register(http_server)
        http_server.register_path("GET", self.get_pattern(),
                                  self.on_GET)

    def on_GET(self, request, *url_args):
        raise NotImplementedError("on_GET callback not implemented")


class PostEventMixin(object):

    """ A mixin with the ability to handle POSTs. """

    def register(self, http_server):
        super(PostEventMixin, self).register(http_server)
        http_server.register_path("POST", self.get_pattern(),
                                  self.on_POST)

    def on_POST(self, request, *url_args):
        raise NotImplementedError("on_POST callback not implemented")


class DeleteEventMixin(object):

    """ A mixin with the ability to handle DELETEs. """

    def register(self, http_server):
        super(DeleteEventMixin, self).register(http_server)
        http_server.register_path("DELETE", self.get_pattern(),
                                  self.on_DELETE)

    def on_DELETE(self, request, *url_args):
        raise NotImplementedError("on_DELETE callback not implemented")


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

    def get_event_data(self, db_dict):
        db_dict.pop("id")
        if "content" in db_dict:
            db_dict["content"] = json.loads(db_dict["content"])
        db_dict["type"] = self.get_event_type()
        return db_dict

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


class InvalidHttpRequestError(CodeMessageException):
    """ Raised when an invalid request was submitted from the client.

    This class provides the ability to get a suitable return HTTP status
    code and body to send back to the client.
    """

    def __init__(self, code, body, json_wrap=True):
        super(InvalidHttpRequestError, self).__init__(code, body)
        if json_wrap:
            self.http_body = cs_error(body, code)
        else:
            self.http_body = body

    def get_status_code(self):
        """ Returns a suitable HTTP status code for this exception. """
        return self.code

    def get_response_body(self):
        """ Returns a suitable HTTP response body for this exception. """
        return self.http_body
