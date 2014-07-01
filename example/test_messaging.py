# -*- coding: utf-8 -*-

""" This is an example of using the server to server implementation to do a
basic chat style thing. It accepts commands from stdin and outputs to stdout.

It assumes that ucids are of the form <user>@<domain>, and uses <domain> as
the address of the remote home server to hit.

Usage:
    python test_messaging.py <port>

Currently assumes the local address is localhost:<port>

"""

from synapse.protocol.http import TwistedHttpServer, TwistedHttpClient
from synapse.transport import TransportLayer
from synapse.transaction import TransactionLayer
from synapse.pdu import PduLayer
from synapse.messaging import MessagingLayer, MessagingCallbacks

from synapse.util import dbutils
from synapse.util import stringutils

from twisted.internet import reactor, defer
from twisted.enterprise import adbapi
from twisted.python.log import PythonLoggingObserver

import argparse
import json
import logging
import re
import sqlite3

import cursesio
import curses.wrapper


logger = logging.getLogger("example")


class InputOutput(object):
    """ This is responsible for basic I/O so that a user can interact with
    the example app.
    """

    def __init__(self, screen, user):
        self.screen = screen
        self.user = user

    def set_home_server(self, server):
        self.server = server

    def on_line(self, line):
        """ This is where we process commands.
        """

        try:
            m = re.match("^join (\S+)$", line)
            if m:
                # The `sender` wants to join a room.
                room_name, = m.groups()
                self.print_line("%s joining %s" % (self.user, room_name))
                self.server.join_room(room_name, self.user, self.user)
                #self.print_line("OK.")
                return

            m = re.match("^invite (\S+) (\S+)$", line)
            if m:
                # `sender` wants to invite someone to a room
                room_name, invitee = m.groups()
                self.print_line("%s invited to %s" % (invitee, room_name))
                self.server.invite_to_room(room_name, self.user, invitee)
                #self.print_line("OK.")
                return

            m = re.match("^send (\S+) (.*)$", line)
            if m:
                # `sender` wants to message a room
                room_name, body = m.groups()
                self.print_line("%s send to %s" % (self.user, room_name))
                self.server.send_message(room_name, self.user, body)
                #self.print_line("OK.")
                return

            m = re.match("^paginate (\S+)$", line)
            if m:
                # we want to paginate a room
                room_name, = m.groups()
                self.print_line("paginate %s" % room_name)
                self.server.paginate(room_name)
                return

            self.print_line("Unrecognized command")

        except Exception as e:
            logger.exception(e)

    def print_line(self, text):
        self.screen.print_line(text)


class Room(object):
    """ Used to store (in memory) the current membership state of a room, and
    which home servers we should send PDUs associated with the room to.
    """
    def __init__(self, room_name):
        self.room_name = room_name
        self.invited = set()
        self.participants = set()
        self.servers = set()

        self.oldest_server = None

        self.have_got_metadata = False

    def add_participant(self, participant):
        """ Someone has joined the room
        """
        self.participants.add(participant)
        self.invited.discard(participant)

        server = stringutils.origin_from_ucid(participant)
        self.servers.add(server)

        if not self.oldest_server:
            self.oldest_server = server

    def add_invited(self, invitee):
        """ Someone has been invited to the room
        """
        self.invited.add(invitee)
        self.servers.add(stringutils.origin_from_ucid(invitee))


class HomeServer(MessagingCallbacks):
    """ A very basic home server implentation that allows people to join a
    room and then invite other people.
    """
    def __init__(self, server_name, messaging_layer, output):
        self.server_name = server_name
        self.messaging_layer = messaging_layer
        self.messaging_layer.set_callback(self)

        self.joined_rooms = {}

        self.output = output

    def on_receive_pdu(self, pdu):
        """ We just received a PDU
        """
        pdu_type = pdu.pdu_type

        if pdu_type == "message":
            self._on_message(pdu)
        else:
            self.output.print_line("#%s (unrec) %s = %s" %
                (pdu.context, pdu.pdu_type, json.dumps(pdu.content))
            )
        #elif pdu_type == "membership":
            #if "joinee" in pdu.content:
                #self._on_join(pdu.context, pdu.content["joinee"])
            #elif "invitee" in pdu.content:
            #self._on_invite(pdu.origin, pdu.context, pdu.content["invitee"])

    def on_state_change(self, pdu):
        #self.output.print_line("#%s (state) %s *** %s" %
                #(pdu.context, pdu.state_key, pdu.pdu_type)
            #)

        if "joinee" in pdu.content:
            self._on_join(pdu.context, pdu.content["joinee"])
        elif "invitee" in pdu.content:
            self._on_invite(pdu.origin, pdu.context, pdu.content["invitee"])

    def _on_message(self, pdu):
        """ We received a message
        """
        self.output.print_line("#%s %s %s" %
                (pdu.context, pdu.content["sender"], pdu.content["body"])
            )

    def _on_join(self, context, joinee):
        """ Someone has joined a room, either a remote user or a local user
        """
        room = self._get_or_create_room(context)
        room.add_participant(joinee)

        self.output.print_line("#%s %s %s" %
                (context, joinee, "*** JOINED")
            )

    def _on_invite(self, origin, context, invitee):
        """ Someone has been invited
        """
        room = self._get_or_create_room(context)
        room.add_invited(invitee)

        self.output.print_line("#%s %s %s" %
                (context, invitee, "*** INVITED")
            )

        if not room.have_got_metadata and origin is not self.server_name:
            logger.debug("Get room state")
            self.messaging_layer.get_context_state(origin, context)
            room.have_got_metadata = True

    @defer.inlineCallbacks
    def send_message(self, room_name, sender, body):
        """ Send a message to a room!
        """
        try:
            yield self.messaging_layer.send(
                    context=room_name,
                    pdu_type="message",
                    content={"sender": sender, "body": body}
                )
        except Exception as e:
            logger.exception(e)

    @defer.inlineCallbacks
    def join_room(self, room_name, sender, joinee):
        """ Join a room!
        """
        self._on_join(room_name, joinee)

        try:
            yield self.messaging_layer.send_state(
                    context=room_name,
                    pdu_type="membership",
                    state_key=joinee,
                    content={"sender": sender, "joinee": joinee}
                )
        except Exception as e:
            logger.exception(e)

    @defer.inlineCallbacks
    def invite_to_room(self, room_name, sender, invitee):
        """ Invite someone to a room!
        """
        self._on_invite(self.server_name, room_name, invitee)

        try:
            yield self.messaging_layer.send_state(
                    context=room_name,
                    pdu_type="membership",
                    state_key=invitee,
                    content={"sender": sender, "invitee": invitee}
                )
        except Exception as e:
            logger.exception(e)

    def paginate(self, room_name, limit=5):
        room = self.joined_rooms.get(room_name)

        if not room:
            return

        dest = room.oldest_server

        return self.messaging_layer.paginate(dest, room_name, limit)

    def _get_room_remote_servers(self, room_name):
        return [i for i in self.joined_rooms.setdefault(room_name,).servers]

    def _get_or_create_room(self, room_name):
        return self.joined_rooms.setdefault(room_name, Room(room_name))

    def get_servers_for_context(self, context):
        return defer.succeed(
                self.joined_rooms.setdefault(context, Room(context)).servers
            )


def setup_db(db_name):
    """ Set up all the dbs. Since all the *.sql have IF NOT EXISTS, so we don't
    have to worry.
    """
    pool = adbapi.ConnectionPool(
        'sqlite3', db_name, check_same_thread=False,
        cp_min=1, cp_max=1)

    dbutils.set_db_pool(pool)

    schemas = [
            "schema/transactions.sql",
            "schema/pdu.sql"
        ]

    for sql_loc in schemas:
        with open(sql_loc, "r") as sql_file:
            sql_script = sql_file.read()

        with sqlite3.connect(db_name) as db_conn:
            c = db_conn.cursor()
            c.executescript(sql_script)
            c.close()
            db_conn.commit()


def main(stdscr):
    parser = argparse.ArgumentParser()
    parser.add_argument('user', type=str)
    parser.add_argument('-v', '--verbose', action='count')
    args = parser.parse_args()

    user = args.user
    server_name = stringutils.origin_from_ucid(user)

    ## Set up logging ##

    root_logger = logging.getLogger()

    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - '
            '%(message)s')
    fh = logging.FileHandler("logs/%s" % user)
    fh.setFormatter(formatter)

    root_logger.addHandler(fh)
    root_logger.setLevel(logging.DEBUG)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)

    if args.verbose > 1:
        root_logger.addHandler(sh)
    elif args.verbose == 1:
        logger.addHandler(sh)

    observer = PythonLoggingObserver()
    observer.start()

    ## Set up db ##

    setup_db("dbs/%s" % user)

    ## Set up synapse server

    curses_stdio = cursesio.CursesStdIO(stdscr)
    input_output = InputOutput(curses_stdio, user)

    curses_stdio.set_callback(input_output)

    http_server = TwistedHttpServer()
    http_client = TwistedHttpClient()

    transport_layer = TransportLayer(server_name, http_server, http_client)
    transaction_layer = TransactionLayer(server_name, transport_layer)
    pdu_layer = PduLayer(transport_layer, transaction_layer)

    messaging = MessagingLayer(server_name, transport_layer, pdu_layer)

    hs = HomeServer(server_name, messaging, curses_stdio)

    input_output.set_home_server(hs)

    ## Start! ##

    try:
        port = int(server_name.split(":")[1])
    except:
        port = 12345

    http_server.start_listening(port)

    reactor.addReader(curses_stdio)

    reactor.run()


if __name__ == "__main__":
    curses.wrapper(main)
