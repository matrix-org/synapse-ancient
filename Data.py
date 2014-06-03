from twisted.internet import defer, reactor
from twisted.enterprise import adbapi
from twistar.dbobject import DBObject
from twistar.registry import Registry
from twistar.utils import createInstances

from Transaction import TransactionCallbacks

import argparse
import sqlite3
import time
import json
import random


class PduLayer(TransactionCallbacks):
    pass


class PDU(DBObject):
    TABLENAME = "pdus"  # Table name
    _next_pdu_id = int(time.time())  # XXX Temp. hack to make it unique

    def create(context, pdu_type, origin, ts, content):
        p_id = PDU._next_pdu_id
        PDU._next_pdu_id += 1
        return PDU(
                pdu_id=p_id,
                context=context,
                pdu_type=pdu_type,
                origin=origin,
                ts=ts,
                content=content
            )

    @defer.inlineCallbacks
    def get_current_metadata_pdus(context):
        result = yield Registry.DBPOOL.runQuery(
                "SELECT pdus.* from metadata_pdu "
                "LEFT JOIN pdus ON metadata_pdu.pdu_row_id = pdus.id "
                "WHERE context = ?",
                (context,)
            )
        instances = yield createInstances(PDU, result)
        defer.returnValue(instances)
        return


class MetadataPDU(DBObject):
    TABLENAME = "metadata_pdu"
    BELONGSTO = [
            {'association_foreign_key': 'pdu_row_id', 'class_name': 'PDU'}
        ]

    def create_from_pdu(pdu, key):
        return MetadataPDU(
                pdu_row_id=pdu.id,
                pdi_context=pdu.context,
                pdu_type=pdu.pdu_type,
                key=key
            )


def setup_db(db_name):
    with open("schema/pdu.sql", "r") as sql_file:
        sql_script = sql_file.read()

    with sqlite3.connect(db_name) as db_conn:
        c = db_conn.cursor()

        c.execute("DROP TABLE IF EXISTS data")
        c.execute("DROP TABLE IF EXISTS metadata")
        c.executescript(sql_script)

        c.close()
        db_conn.commit()


def get_origin(ucid):
    return ucid.split("@", 1)[1]


class SynapseDataLayer(object):
    def __init__(self, server_name, db_name, transaction_layer):
        self.server_name = server_name
        self.transaction_layer = transaction_layer

        self.transaction_layer.set_data_layer(self)

        setup_db(db_name)

        def set_row_factory(d):
            d.row_factory = sqlite3.Row

        self.__db_pool = adbapi.ConnectionPool(
                'sqlite3',
                db_name,
                check_same_thread=False,
                cp_openfun=set_row_factory
            )

        self.message_layer = None

    def set_message_layer(self, message_layer):
        self.message_layer = message_layer

    @defer.inlineCallbacks
    def on_data(self, origin, ts, version, content):
        saw_ts = int(time.time() * 1000)

        yield self.message_layer.on_data(origin, ts, content)

        yield self._record_data(origin, saw_ts, content)

        # Check to see if we have seen this message. If not, request it.
        if content["type"] == "feedback":
            feedback_origin = content["feedback_origin"]
            feedback_msg_id = content["feedback_msg_id"]
            seen = yield self.have_seen_message(
                feedback_origin, feedback_msg_id)
            if not seen:
                self.transaction_layer.get_message(
                    origin, feedback_origin, feedback_msg_id)

    @defer.inlineCallbacks
    def have_seen_message(self, origin, data_id):
        query = "SELECT * FROM data where origin=? and data_id=?"
        res = yield self.__db_pool.runQuery(query, (origin, data_id,))
        defer.returnValue(len(res) > 0)

    @defer.inlineCallbacks
    def _record_data(self, origin, ts, content):
        data_id = content["data_id"]
        context = content["context"]
        data_type = content["type"]

        if "metadata" in content:
            is_metadata = bool(content["metadata"])
        else:
            is_metadata = False

        if is_metadata:
            yield self._record_metadata(origin, ts, content)

        query = "INSERT OR REPLACE INTO data "\
            "(data_id, context, type, origin, ts, data) "\
            "VALUES (?,?,?,?,?,?)"
        yield self.__db_pool.runQuery(
            query,
            (data_id, context, data_type, origin,
                ts, json.dumps(content), )
        )

    @defer.inlineCallbacks
    def _record_metadata(self, origin, ts, content):
        data_id = content["data_id"]
        context = content["context"]
        data_type = content["type"]
        key = content["key"]

        query = "INSERT OR REPLACE INTO metadata "\
            "(msg_id, origin, room_id, type, key) "\
            "VALUES (?,?,?,?,?)"

        yield self.__db_pool.runQuery(
            query,
            (data_id, origin, context, data_type, key, )
        )

    @defer.inlineCallbacks
    def on_get_message(self, msg_origin, msg_id):
        query = "select * from data where msg_id=? and origin=?"
        rows = yield self.__db_pool.runQuery(query, (msg_id, msg_origin,))

        data = [json.loads(r["data"]) for r in rows]

        defer.returnValue(data)

    @defer.inlineCallbacks
    def on_get_metadata(self, room_id):
        query = "SELECT "\
                "data.data as data "\
            "FROM data "\
            "INNER JOIN metadata ON data.msg_id = metadata.msg_id "\
            "where data.room_id=?"
        rows = yield self.__db_pool.runQuery(query, (room_id,))

        data = [json.loads(r["data"]) for r in rows]

        defer.returnValue(data)

    @defer.inlineCallbacks
    def send_data(self, recipients, data, ts):
        yield self._record_data(self.server_name, ts, data)

        r = yield self.transaction_layer.send(recipients, data, ts)
        defer.returnValue(r)

    def get_metadata(self, destination, room_id):
        return self.transaction_layer.get_metadata(destination, room_id)

    @defer.inlineCallbacks
    def send_feedback(self, origin, msg_id, recipients):
        msg = {
            "type": "feedback",
            "msg_id": str(random.randint(0, 1000000)),
            "room_id": None,
            "feedback_msg_id": msg_id,
            "feedback_origin": origin
        }

        yield self.transaction_layer.send(
            recipients, msg, int(time.time() * 1000)
        )


if __name__ == "__main__":
    import Transport
    import Transaction

    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=int)
    args = parser.parse_args()

    db_name = "dbs/test-%d.db" % args.port

    sTransport = Transport.SynapseHttpTransportLayer()
    sServer = Transaction.HttpTransactionLayer(
        "localhost:4000", db_name, sTransport)
    sTransport.start_listening(4000)

    sData = SynapseDataLayer("localhost:4000", db_name, sTransport)

    reactor.run()
