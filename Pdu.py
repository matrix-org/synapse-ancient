from twisted.internet import defer, reactor
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
    def send_pdu(self, pdu):
        """ Sends data to a group of remote home servers
        """
        pass

    def trigger_get_context_metadata(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass


class PduCallbacks(object):
    def on_receive_pdu(self, pdu):
        pass


class PDU(DBObject):
    """ Persists PDUs into a db.

        This automagically recognizes metadata PDUs and keeps the metadata
        PDUs table up to date.

        Properties:
            - pdu_id
            - context
            - pdu_type
            - origin
            - ts
            - content (automatically converts into content_json)
            - is_metadata
            - metadata_key
    """

    TABLENAME = "pdus"  # Table name
    _next_pdu_id = int(time.time())  # XXX Temp. hack to make it unique

    def create(context, pdu_type, origin, ts, content,
            is_metadata=True, metadata_key=None):
        p_id = PDU._next_pdu_id
        PDU._next_pdu_id += 1
        return PDU(
                pdu_id=p_id,
                context=context,
                pdu_type=pdu_type,
                origin=origin,
                ts=ts,
                content=content,
                is_metadata=is_metadata,
                metadata_key=metadata_key
            )

    @defer.inlineCallbacks
    def get_current_metadata_pdus(context):
        """ Get all current metatdata PDUs for a given context.
            See MetadataPDU below.
        """
        result = yield Registry.DBPOOL.runQuery(
                "SELECT pdus.* from metadata_pdu "
                "LEFT JOIN pdus ON metadata_pdu.pdu_row_id = pdus.id "
                "WHERE context = ?",
                (context,)
            )
        instances = yield createInstances(PDU, result)
        defer.returnValue(instances)
        return

    # INTERNAL
    @defer.inlineCallbacks
    def beforeSave(self):
        # Automagically store self.content as json in content_json column
        if self.content:
            self.content_json = json.dumps(self.content)

        if (self.is_metadata):
            # Just create a new one and insert it. This will replace anything
            # already in there correctly anyway.
            m_pdu = _MetadataPDU.create_from_pdu(self)
            yield m_pdu.save()

        defer.returnValue(True)

    # INTERNAL
    def afterInit(self):
        # Automagically store self.content as json in content_json column
        if self.content_json:
            self.content = json.loads(self.content_json)

        return True

    # INTERNAL
    @defer.inlineCallbacks
    def refresh(self):
        ret = yield super(DBObject, self).refresh()

        # Automagically store self.content as json in content_json column
        if self.content_json:
            self.content = json.loads(self.content_json)

        defer.returnValue(ret)


class _MetadataPDU(DBObject):
    """ For a given context, we need to be able to efficiently get PDUs that
        are considered to be a) metadata and b) "current"
        Metadata pdu's are considered current if we have not since seen any
        pdu's with the same (context, pdu_type, metadata_key) tuple.
        We do this by keeping the track of "current" metata PDUs in a seperate
        table.
    """
    TABLENAME = "metadata_pdu"

    def create_from_pdu(pdu):
        return _MetadataPDU(
                pdu_row_id=pdu.id,
                pdi_context=pdu.context,
                pdu_type=pdu.pdu_type,
                key=pdu.key
            )


def setup_db(db_name):
    with open("schema/pdu.sql", "r") as sql_file:
        sql_script = sql_file.read()

    with sqlite3.connect(db_name) as db_conn:
        c = db_conn.cursor()

        c.execute("DROP TABLE IF EXISTS pdus")
        c.execute("DROP TABLE IF EXISTS metadata_pdu")
        c.executescript(sql_script)

        c.close()
        db_conn.commit()


def get_origin(ucid):
    return ucid.split("@", 1)[1]


class SynapseDataLayer(PduLayer):
    def __init__(self, server_name, db_name, transaction_layer):
        self.server_name = server_name
        self.transaction_layer = transaction_layer

        self.transaction_layer.set_data_layer(self)

        setup_db(db_name)

        self.message_layer = None

    def on_pdu_request(pdu_origin, pdu_id):
        """ Get's called when we want to get a specific pdu
            Returns a dict representing the pdu
        """
        pass

    def on_get_context_metadata(context):
        """ Get's called when we want to get all metadata pdus for a given
            context.
            Returns a list of dicts.
        """
        pass

    def on_received_transaction(transaction):
        """ Get's called when we receive a transaction with a bunch of pdus.

            Returns a deferred with a tuple of (code, response_json)
        """
        pass

    def send_pdu(self, pdu):
        """ Sends data to a group of remote home servers
        """
        pass

    def trigger_get_context_metadata(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        pass

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        """ Tries to get the remote home server ("destination") to give us
            the given pdu that was from the given ("pdu_origin") server
        """
        pass

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
