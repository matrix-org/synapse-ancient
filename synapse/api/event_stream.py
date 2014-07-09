# -*- coding: utf-8 -*-
from twisted.internet import defer

from dbobjects import Message
from events import GetEventMixin, BaseEvent, InvalidHttpRequestError
from auth import AccessTokenAuth

import re


class EventStream(GetEventMixin, BaseEvent):

    @classmethod
    def get_pattern(cls):
        return re.compile("^/events$")

    @AccessTokenAuth.defer_authenticate
    @defer.inlineCallbacks
    def on_GET(self, request, auth_user_id=None):
        try:
            self._check_query_parameters(request)
        except InvalidHttpRequestError as e:
            return (e.get_status_code(), e.get_response_body())

        return (200, "This is not the stream you are looking for.")

    def _check_query_parameters(self, request):
        try:
            if request.args["dir"][0] not in ["f", "b", "forwards",
                                              "backwards"]:
                raise InvalidHttpRequestError(400, "Unknown dir value.")
        except KeyError:
            pass  # dir is optional


@staticmethod
def get_messages(self, room_id=None, from_version=None, to_version=None,
                 **kwargs):
    where_dict = self._build_where_version(from_version, to_version)
    if room_id:
        where_dict["where"] += " AND room_id = ?"
        where_dict["params"].append(room_id)

    where_arr = [where_dict["where"]] + where_dict["params"]
    return Message.find(
        where=where_arr,
        orderby=where_dict["orderby"],
        **kwargs
    )
