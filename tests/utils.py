from synapse.http.server import HttpServer
from synapse.api.errors import cs_error, CodeMessageException, StoreError
from synapse.api.constants import Membership

from synapse.api.events.room import (
    RoomMemberEvent, MessageEvent
)

from twisted.internet import defer

from collections import namedtuple
from mock import patch, Mock
import json
import urlparse


class MockHttpServer(HttpServer):

    def __init__(self, prefix=""):
        self.callbacks = []  # 3-tuple of method/pattern/function
        self.prefix = prefix

    def trigger_get(self, path):
        return self.trigger("GET", path, None)

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
        path = self.prefix + path

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
            path = mock_request.path
        except:
            pass

        for (method, pattern, func) in self.callbacks:
            if http_method != method:
                continue

            matcher = pattern.match(path)
            if matcher:
                try:
                    (code, response) = yield func(
                        mock_request,
                        *matcher.groups()
                    )
                    defer.returnValue((code, response))
                except CodeMessageException as e:
                    defer.returnValue((e.code, cs_error(e.msg)))

        raise KeyError("No event can handle %s" % path)

    def register_path(self, method, path_pattern, callback):
        self.callbacks.append((method, path_pattern, callback))


class MemoryDataStore(object):

    RoomMember = namedtuple(
        "RoomMember",
        ["room_id", "user_id", "sender", "membership", "content"]
    )

    PathData = namedtuple("PathData",
                          ["room_id", "path", "content"])

    Message = namedtuple("Message",
                         ["room_id", "msg_id", "user_id", "content"])

    Room = namedtuple("Room",
                      ["room_id", "is_public", "creator"])

    def __init__(self):
        self.tokens_to_users = {}
        self.paths_to_content = {}
        self.members = {}
        self.messages = {}
        self.rooms = {}
        self.room_members = {}

    def register(self, user_id, token):
        if user_id in self.tokens_to_users.values():
            raise StoreError(400, "User in use.")
        self.tokens_to_users[token] = user_id

    def get_user(self, token=None):
        try:
            return self.tokens_to_users[token]
        except:
            raise StoreError(400, "User does not exist.")

    def get_room(self, room_id):
        try:
            return self.rooms[room_id]
        except:
            return None

    def store_room(self, room_id=None, room_creator_user_id=None,
                              is_public=None):
        if room_id in self.rooms:
            raise StoreError(409, "Conflicting room!")

        room = MemoryDataStore.Room(room_id=room_id, is_public=is_public,
                    creator=room_creator_user_id)
        self.rooms[room_id] = room
        #self.store_room_member(user_id=room_creator_user_id, room_id=room_id,
                               #membership=Membership.JOIN,
                               #content={"membership": Membership.JOIN})

    def get_message(self, user_id=None, room_id=None, msg_id=None):
        try:
            return self.messages[user_id + room_id + msg_id]
        except:
            return None

    def store_message(self, user_id=None, room_id=None, msg_id=None,
                      content=None):
        msg = MemoryDataStore.Message(room_id=room_id, msg_id=msg_id,
                    user_id=user_id, content=content)
        self.messages[user_id + room_id + msg_id] = msg

    def get_room_member(self, user_id=None, room_id=None):
        try:
            return self.members[user_id + room_id]
        except:
            return None

    def get_room_members(self, room_id=None, membership=None):
        try:
            return self.room_members[room_id]
        except:
            return None

    def get_rooms_for_user_where_membership_is(self, user_id, membership_list):
        return [r for r in self.room_members
                if user_id in self.room_members[r]]

    def store_room_member(self, user_id=None, sender=None, room_id=None,
                          membership=None, content=None):
        member = MemoryDataStore.RoomMember(room_id=room_id, user_id=user_id,
            sender=sender, membership=membership, content=json.dumps(content))
        self.members[user_id + room_id] = member

        # TODO should be latest state
        if room_id not in self.room_members:
            self.room_members[room_id] = []
        self.room_members[room_id].append(member)

    def get_room_data(self, room_id, etype, state_key=""):
        path = "%s-%s-%s" % (room_id, etype, state_key)
        try:
            return self.paths_to_content[path]
        except:
            return None

    def store_room_data(self, room_id, etype, state_key="", content=None):
        path = "%s-%s-%s" % (room_id, etype, state_key)
        data = MemoryDataStore.PathData(path=path, room_id=room_id,
                    content=content)
        self.paths_to_content[path] = data

    def get_message_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0, with_feedback=False):
        return ([], from_key)  # TODO

    def get_room_member_stream(self, user_id=None, from_key=None, to_key=None):
        return ([], from_key)  # TODO

    def get_feedback_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0):
        return ([], from_key)  # TODO

    def get_room_data_stream(self, user_id=None, from_key=None, to_key=None,
                            room_id=None, limit=0):
        return ([], from_key)  # TODO

    def to_events(self, data_store_list):
        return data_store_list  # TODO

    def get_max_message_id(self):
        return 0  # TODO

    def get_max_feedback_id(self):
        return 0  # TODO

    def get_max_room_member_id(self):
        return 0  # TODO

    def get_max_room_data_id(self):
        return 0  # TODO

    def get_joined_hosts_for_room(self, room_id):
        return defer.succeed([])

    def persist_event(self, event):
        if event.type == MessageEvent.TYPE:
            return self.store_message(
                user_id=event.user_id,
                room_id=event.room_id,
                msg_id=event.msg_id,
                content=json.dumps(event.content)
            )
        elif event.type == RoomMemberEvent.TYPE:
            return self.store_room_member(
                user_id=event.target_user_id,
                room_id=event.room_id,
                content=event.content,
                membership=event.content["membership"]
            )
        else:
            raise NotImplementedError(
                "Don't know how to persist type=%s" % event.type
            )

    def set_presence_state(self, user_localpart, state):
        return defer.succeed({"state": 0})

    def get_presence_list(self, user_localpart, accepted):
        return []
