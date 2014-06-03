from twisted.internet import defer, reactor, stdio
from twisted.enterprise import adbapi
from twisted.protocols import basic

import argparse
import logging
import sqlite3
import time
import random


def setup_db(db_name):
    db_conn = sqlite3.connect(db_name)
    c = db_conn.cursor()
    c.execute("DROP TABLE IF EXISTS messages")
    c.execute("DROP TABLE IF EXISTS members")
    c.execute("DROP TABLE IF EXISTS rooms")
    c.execute("CREATE TABLE IF NOT EXISTS messages("
            "msg_id, "
            "room_id, "
            "origin TEXT, "
            "sender TEXT, "
            "ts INTEGER, "
            "body TEXT"
        ")"
    )
    c.execute("CREATE TABLE IF NOT EXISTS members(room_id, ucid, ts INTEGER)")
    c.execute("CREATE TABLE IF NOT EXISTS rooms(room_id)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS message_id ON "
        "messages(msg_id, origin)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS members_id ON "
        "members(room_id, ucid)")
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS rooms_id ON "
        "rooms(room_id)")
    c.close()
    db_conn.commit()
    db_conn.close()


def get_origin(ucid):
    return ucid.split("@", 1)[1]


class MessagingLayer:
    def __init__(self, db_name, data_layer):
        self.data_layer = data_layer
        self.data_layer.set_message_layer(self)

        setup_db(db_name)

        def set_row_factory(d):
            d.row_factory = sqlite3.Row

        self.__db_pool = adbapi.ConnectionPool(
                'sqlite3',
                db_name,
                check_same_thread=False,
                cp_openfun=set_row_factory
            )

    def on_data(self, origin, ts, content):
        msg_type = content["type"]

        if msg_type == "msg":
            return self._on_message(origin, ts, content)
        elif msg_type == "join":
            return self._on_join(origin, ts, content)
        elif msg_type == "feedback":
            return defer.succeed(None)

        # we need to handle feedback.

        return defer.fail(RuntimeError("Unknown msg type %s" % msg_type))

    @defer.inlineCallbacks
    def _on_message(self, origin, ts, msg):
        sender = msg["sender"]
        body = msg["body"]
        msg_id = msg["msg_id"]
        room_id = msg["room_id"]

        origin = get_origin(sender)

        # We need to send feedback.

        print "%s: %s" % (room_id, body)

        query = "INSERT OR IGNORE INTO messages "\
            "(msg_id, room_id, origin, sender, ts, body) values (?,?,?,?,?,?)"

        yield self.__db_pool.runQuery(
            query,
            (msg_id, room_id, origin, sender, int(time.time() * 1000), body,)
        )

        self.send_feedback_to_room(origin, msg_id, room_id)

    @defer.inlineCallbacks
    def send_feedback_to_room(self, origin, msg_id, room_id):
        recipients = yield self._get_room_servers(room_id)

        self.data_layer.send_feedback(origin, msg_id, recipients)

    @defer.inlineCallbacks
    def _on_join(self, origin, ts, content):
        joinee = content["key"]
        room_id = content["room_id"]
        msg_id = content["msg_id"]

        query = "INSERT OR IGNORE INTO members "\
            "(room_id, ucid, ts) values (?,?,?)"

        yield self.__db_pool.runQuery(
            query,
            (room_id, joinee, int(time.time() * 1000),)
        )

        def add_room(txn, rid):
            txn.execute("INSERT OR IGNORE INTO rooms "
                "(room_id) values (?)", (rid,))
            return txn.rowcount

        # If we haven't seen this room before, ask for metadata
        rowcount = yield self.__db_pool.runInteraction(add_room, room_id)
        if rowcount == 1:
            # We don't yield here as we don't want to block the PUT from
            # finishing.
            self.data_layer.get_metadata(origin, room_id)

        self.send_feedback_to_room(origin, msg_id, room_id)

    @defer.inlineCallbacks
    def send_message(self, sender, room_id, body):
        msg = {
            "type": "msg",
            "sender": sender,
            "room_id": room_id,
            "body": body,
            "msg_id": str(random.randint(0, 1000000))
        }

        recipients = yield self._get_room_servers(room_id)

        r = yield self.data_layer.send_data(
            recipients,
            msg,
            int(time.time() * 1000)
        )

        defer.returnValue(r)

    @defer.inlineCallbacks
    def _get_room_servers(self, room_id):
        query = "SELECT ucid FROM members WHERE room_id=?"
        rows = yield self.__db_pool.runQuery(query, (room_id,))

        defer.returnValue(
            [get_origin(r["ucid"]).encode("UTF-8") for r in rows]
        )

    @defer.inlineCallbacks
    def send_join(self, room_id, joinee):
        # msg = {"type": "join", "room_id": room_id, "sender": joinee}

        msg = {
            "type": "join",
            "key": joinee,
            "room_id": room_id,
            "metadata": True,
            "msg_id": str(random.randint(0, 1000000))
        }

        query = "INSERT OR IGNORE INTO members "\
            "(room_id, ucid, ts) values (?,?,?)"
        yield self.__db_pool.runQuery(
            query,
            (room_id, joinee, int(time.time() * 1000),)
        )

        query = "SELECT ucid FROM members WHERE room_id=?"
        rows = yield self.__db_pool.runQuery(query, (room_id,))

        recipients = [get_origin(r["ucid"]).encode("UTF-8") for r in rows]

        r = yield self.data_layer.send_data(
            recipients,
            msg,
            int(time.time() * 1000)
        )

    @defer.inlineCallbacks
    def send_message_partial(self, sender, room_id, body, recipient):
        # This function sends a message to a room, but only actually
        # notifies a single user.

        msg = {
            "type": "msg",
            "sender": sender,
            "room_id": room_id,
            "body": body,
            "msg_id": str(random.randint(0, 1000000))
        }

        recipients = [get_origin(recipient)]

        r = yield self.data_layer.send_data(
            recipients,
            msg,
            int(time.time() * 1000)
        )

        defer.returnValue(r)


class LineReader(basic.LineReceiver):
    delimiter = '\n'

    def __init__(self, message_layer):
        self.message_layer = message_layer

    def connectionMade(self):
        self.transport.write('>>> ')

    def lineReceived(self, line):
        #self.sendLine('Echo: ' + line)
        try:
            if not line:
                return

            cmd, room_id, data = line.split(" ", 2)

            if cmd == "msg":
                sender, body = data.split(" ", 1)
                self.message_layer.send_message(sender, room_id, body)
                self.sendLine("OK")
            elif cmd == "partial":
                sender, receiver, body = data.split(" ", 2)
                self.message_layer.send_message_partial(
                    sender, room_id, body, receiver)
                self.sendLine("OK")
            elif cmd == "add":
                self.message_layer.send_join(room_id, data)
                self.sendLine("OK")
            elif cmd == "create":
                self.message_layer.send_join(room_id, data)
                self.sendLine("OK")
        except Exception as e:
            logging.exception(e)
        finally:
            self.transport.write('>>> ')

if __name__ == "__main__":
    import Data
    import Transaction
    import Transport

    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int)
    args = parser.parse_args()

    db_name = "dbs/test-%d.db" % args.port
    sever_name = "localhost:%d" % args.port

    sTransport = Transport.SynapseHttpTransportLayer()
    sTransaction = Transaction.HttpTransactionLayer(
        sever_name,
        db_name,
        sTransport
    )

    sData = Data.SynapseDataLayer(sever_name, db_name, sTransaction)

    sServer = MessagingLayer(db_name, sData)

    sTransport.start_listening(args.port)

    stdio.StandardIO(LineReader(sServer))

    reactor.run()
