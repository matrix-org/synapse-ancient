# -*- coding: utf-8 -*-

""" This is an example of using the server to server implementation to do a
basic chat style thing. It accepts commands from stdin and outputs to stdout.

It assumes that ucids are of the form <user>@<domain>, and uses <domain> as
the address of the remote home server to hit.

Usage:
    python test_messaging.py <port>

Currently assumes the local address is localhost:<port>


"""

from synapse.http_wrapper import TwsitedHttpServer, TwistedHttpClient
from synapse.transport import HttpTransportLayer
from synapse.transaction import HttpTransactionLayer
from synapse.pdu import SynapsePduLayer
from synapse.messaging import MessagingImpl, MessagingCallbacks

from synapse.protocol.units import Pdu

from synapse import utils

from twisted.internet import stdio, reactor, error
from twisted.protocols import basic
from twisted.enterprise import adbapi
from twistar.registry import Registry
from twisted.python.log import PythonLoggingObserver

import argparse
import logging
import re
import sqlite3


class InputOutput(basic.LineReceiver):
    """ This is responsible for basic I/O so that a user can interact with
    the example app.
    """
    delimiter = '\n'

    def __init__(self):
        self.waiting_for_input = False

    def set_home_server(self, server):
        self.server = server

    def connectionMade(self):
        self.waiting_for_input = True
        self.transport.write('>>> ')

    def lineReceived(self, line):
        """ This is where we process commands.
        """
        self.waiting_for_input = False

        try:
            m = re.match("^join (\S+) (\S+)$", line)
            if m:
                # The `sender` wants to join a room.
                sender, room_name = m.groups()
                self.sendLine("%s joining %s" % (sender, room_name))
                self.server.join_room(room_name, sender, sender)
                self.sendLine("OK.")

            m = re.match("^invite (\S+) (\S+) (\S+)$", line)
            if m:
                # `sender` wants to invite someone to a room
                sender, room_name, invitee = m.groups()
                self.sendLine("%s invited to %s" % (invitee, room_name))
                self.server.invite_to_room(room_name, sender, invitee)
                self.sendLine("OK.")

            m = re.match("^send (\S+) (\S+) (.*)$", line)
            if m:
                # `sender` wants to message a room
                sender, room_name, body = m.groups()
                self.sendLine("%s send to %s" % (sender, room_name))
                self.server.send_message(room_name, sender, body)
                self.sendLine("OK.")

        except Exception as e:
            logging.exception(e)
        finally:
            self.waiting_for_input = True
            self.transport.write('>>> ')

    def print_line(self, text):
        self.sendLine(text.encode('utf8'))

        if self.waiting_for_input:
            self.transport.write('>>> ')

        self.waiting_for_input = True

    def connectionLost(self, reason):
        try:
            reactor.stop()
        except error.ReactorNotRunning:
            pass


class Room(object):
    """ Used to store (in memory) the current membership state of a room, and
    which home servers we should send PDUs associated with the room to.
    """
    def __init__(self, room_name):
        self.room_name = room_name
        self.invited = set()
        self.participants = set()
        self.servers = set()

    def add_participant(self, participant):
        """ Someone has joined the room
        """
        self.participants.add(participant)
        self.invited.discard(participant)

        self.servers.add(utils.origin_from_ucid(participant))

    def add_invited(self, invitee):
        """ Someone has been invited to the room
        """
        self.invited.add(invitee)
        self.servers.add(utils.origin_from_ucid(invitee))


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
        elif pdu_type == "membership":
            if "joinee" in pdu.content:
                self._on_join(pdu.context, pdu.content["joinee"])
            elif "invitee" in pdu.content:
                self._on_invite(pdu.origin, pdu.context, pdu.content["invitee"])

    def _on_message(self, pdu):
        """ We received a message
        """
        self.output.print_line("#%s %s\t %s" %
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
        new_room = context not in self.joined_rooms

        room = self._get_or_create_room(context)
        room.add_invited(invitee)

        self.output.print_line("#%s %s %s" %
                (context, invitee, "*** INVITED")
            )

        if new_room and origin is not self.server_name:
            self.messaging_layer.get_context_state(origin, context)

    def send_message(self, room_name, sender, body):
        """ Send a message to a room!
        """
        pdu = Pdu.create_new(
                context=room_name,
                origin=self.server_name,
                pdu_type="message",
                destinations=self._get_room_remote_servers(room_name),
                content={"sender": sender, "body": body}
            )

        return self.messaging_layer.send_pdu(pdu)

    def join_room(self, room_name, sender, joinee, destination=None):
        """ Join a room!
        """
        self._on_join(room_name, joinee)

        if destination:
            destinations = [destination]
        else:
            self._get_or_create_room(room_name)
            destinations = self._get_room_remote_servers(room_name)

        if destinations:
            self.output.print_line("Sending to " + str(destinations))

            pdu = Pdu.create_new(
                    context=room_name,
                    origin=self.server_name,
                    pdu_type="membership",
                    destinations=destinations,
                    is_state=True,
                    state_key=joinee,
                    content={"sender": sender, "joinee": joinee}
                )

            self.messaging_layer.send_pdu(pdu)

    def invite_to_room(self, room_name, sender, invitee):
        """ Invite someone to a room!
        """
        self._on_invite(self.server_name, room_name, invitee)

        destinations = self._get_room_remote_servers(room_name)

        if destinations:
            self.output.print_line("Sending to " + str(destinations))

            pdu = Pdu.create_new(
                    context=room_name,
                    origin=self.server_name,
                    pdu_type="membership",
                    destinations=destinations,
                    is_state=True,
                    state_key=invitee,
                    content={"sender": sender, "invitee": invitee}
                )

            self.messaging_layer.send_pdu(pdu)

    def _get_room_remote_servers(self, room_name):
        return [i for i in self.joined_rooms.setdefault(room_name,).servers]

    def _get_or_create_room(self, room_name):
        return self.joined_rooms.setdefault(room_name, Room(room_name))


def setup_db(db_name):
    """ Set up all the dbs. Since all the *.sql have IF NOT EXISTS, so we don't
    have to worry.
    """
    Registry.DBPOOL = adbapi.ConnectionPool(
        'sqlite3', database=("dbs/%d") % port, check_same_thread=False)

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


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int)
    args = parser.parse_args()

    port = args.port
    server_name = "localhost:%d" % port

    logging.basicConfig(filename=("logs/%d" % port), level=logging.DEBUG)

    observer = PythonLoggingObserver()
    observer.start()

    setup_db("dbs/%d" % port)

    input_output = InputOutput()

    http_server = TwsitedHttpServer()
    http_client = TwistedHttpClient()

    transport_layer = HttpTransportLayer(server_name, http_server, http_client)
    transaction_layer = HttpTransactionLayer(server_name, transport_layer)
    pdu_layer = SynapsePduLayer(transaction_layer)

    messaging = MessagingImpl(server_name, transport_layer, transaction_layer,
        pdu_layer)

    hs = HomeServer(server_name, messaging, input_output)

    input_output.set_home_server(hs)

    http_server.start_listening(port)

    stdio.StandardIO(input_output)

    reactor.run()