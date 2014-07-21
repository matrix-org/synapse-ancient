# -*- coding: utf-8 -*-
""" This module contains base REST classes for constructing REST events. """
from synapse.api.errors import cs_error, CodeMessageException

import json


class RestEventFactory(object):

    """ A factory for creating REST events.

    These REST events represent the entire client-server REST API. Generally
    speaking, they serve as wrappers around events and the handlers that process
    them.

    See synapse.api.events for information on synapse events.
    """

    events = []

    def __init__(self, handler_fac, event_fac, auth):
        # You get import errors if you try to import before the classes in this
        # file are defined, hence importing here instead.
        import room
        self.events.append(room.RoomTopicRestEvent(handler_fac,
                                                   event_fac, auth))
        self.events.append(room.RoomMemberRestEvent(handler_fac,
                                                    event_fac, auth))
        self.events.append(room.MessageRestEvent(handler_fac,
                                                 event_fac, auth))
        self.events.append(room.RoomCreateRestEvent(handler_fac,
                                                    event_fac, auth))

        from events import EventStreamRestEvent
        self.events.append(EventStreamRestEvent(handler_fac,
                                                event_fac, auth))

        import register
        self.events.append(register.RegisterRestEvent(handler_fac,
                                                      event_fac, auth))

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

    def __init__(self, handler_factory, event_factory, auth):
        self.handler_factory = handler_factory
        self.event_factory = event_factory
        self.auth = auth

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


# XXX: are all these Mixins really the nicest way to handle supporting
# different HTTP methods?  The register() feels like it should be able
# to be automated by inspecting the available methods on a given servlet
# or similar, rather than all this duplicated boilerplate?  -- Matthew

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


class OptionsEventMixin(object):

    """ A mixin with the ability to handle OPTIONS. """

    def register(self, http_server):
        super(OptionsEventMixin, self).register(http_server)
        http_server.register_path("OPTIONS", self.get_pattern(),
                                  self.on_OPTIONS)

    def on_OPTIONS(self, request, *url_args):
        raise NotImplementedError("on_OPTIONS callback not implemented")


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
