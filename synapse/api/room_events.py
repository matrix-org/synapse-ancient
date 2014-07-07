from events import EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent

import re


class RoomTopicEvent(EventStreamMixin, PutEventMixin, GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/topic$")

    def get_event_type(self):
        return "sy.room.topic"

    def on_GET(self, request, *url_args):
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"rooms": "None"})

    def on_PUT(self, request, *url_args):
        try:
            req = BaseEvent.get_valid_json(request.content.read(), ["topic"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"topic": req["topic"]})


class RoomMemberEvent(EventStreamMixin, PutEventMixin, GetEventMixin,
                      BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/rooms/(?P<roomid>[^/]*)/members/" +
                          "(?P<userid>[^/]*)/state$")

    def get_event_type(self):
        return "sy.room.members.state"

    def on_GET(self, request, *url_args):
        print "dict: %s" % self.get_event_stream_dict(url_args)
        return (200, {"membership": "None"})

    def on_PUT(self, request, *url_args):
        try:
            req = BaseEvent.get_valid_json(request.content.read(),
                                           ["membership"])
        except ValueError:
            return (400, BaseEvent.error("Content must be JSON."))
        except KeyError:
            return (400, BaseEvent.error("Missing required keys."))
        return (200, {"membership": req["membership"]})