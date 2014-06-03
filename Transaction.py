from twisted.internet import defer
from twistar.dbobject import DBObject

from Transport import TransportCallbacks, TransportData

import logging
import json
import sqlite3
import time


class TransactionLayer(TransportCallbacks):
    """ The transaction layer is responsible for handling incoming and outgoing
        transactions, as well as other events (e.g. requests for a specific
        pdu)

        For incoming transactions it needs to ignore duplicates, and otherwise
        pass the data upwards. It receives incoming transactions (and other
        events) via the Transport.TransportCallbacks.
        For incoming events it usually passes the request directly onwards

        For outgoing transactions, it needs to convert it to a suitable form
        for the Transport layer to process.
        For outgoing events, we usually pass it straight to the Transport layer
    """

    def send_transaction(self, transaction):
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


class TransactionCallbacks(object):
    """ When the transaction layer receives requests it can't process, we
        send them upwards via these set's of callbacks.
    """

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


class Transaction(DBObject):
    """ Represents a transaction, and includes helper methods
        to encode/decode transactions. It's also responsible for
        persisting the transaction in the transactions table.

        Stores the "pdu_list" as json, and converts it to
        a json encoded string in "data" before storage.

        When loading from the db, will decode the "data"
        column into "pdu_list"
    """

    TABLENAME = "transactions"  # Table name
    _next_transaction_id = int(time.time())  # XXX Temp. hack to make it unique

    def create(ts, origin, destination, pdu_list):
        transaction_id = Transaction._next_transaction_id
        Transaction._next_transaction_id += 1

        return Transaction(
                transaction_id=transaction_id,
                ts=ts,
                destination=destination,
                origin=origin,
                pdu_list=pdu_list,
                response_code=0,
                response=None
            )

    def beforeSave(self):
        # We're about to be saved! Quick update the data!
        self.data = json.dumps(self.pdu_list)

    def afterInit(self):
        if self.data is not None:
            # We were probably loaded from the db, so decode data
            # into pdu_list
            self.pdu_list = json.loads(self.data)

    def from_transport_data(transport_data):
        return Transaction(
                transaction_id=transport_data.transaction_id,
                origin=transport_data.origin,
                pdu_list=transport_data.body["data"],
                ts=transport_data.body["ts"]
            )

    def to_transport_data(self):
        return TransportData(
               origin=self.origin,
               destination=self.destination,
               transaction_id=self.transaction_id,
               body={
                       "origin": self.origin,
                       "data": self.pdu_list,
                       "ts": self.ts
                   }
           )

    def send(self, transaction_layer):
        """ Sends the transaction via the given transaction_layer
        """
        transaction_layer.send_transaction(self)


def _setup_db(db_name):
    """ Creates the necessary tables in the given db.

        * Deletes old data.*
    """

    with open("schema/transactions.sql", "r") as sql_file:
        sql_script = sql_file.read()

    with sqlite3.connect(db_name) as db_conn:
        c = db_conn.cursor()

        c.execute("DROP TABLE IF EXISTS transactions")
        c.executescript(sql_script)

        c.close()
        db_conn.commit()


class HttpTransactionLayer(TransactionLayer):
    def __init__(self, server_name, db_name, transport_layer):
        self.server_name = server_name
        self.db_name = db_name

        _setup_db(db_name)

        self.transport_layer = transport_layer
        self.transport_layer.register_callbacks(self)

        self.data_layer = None

    def set_data_layer(self, data_layer):
        self.data_layer = data_layer

    @defer.inlineCallbacks
    def send_transaction(self, transaction):
        """ Sends a transaction.
        """
        code, response = yield self.transport_layer.send_data(
                transaction.to_transport_data()
            )

        transaction.respone_code = code
        transaction.response = response

        yield transaction.save()

    @defer.inlineCallbacks
    def on_pull_request(self, version):
        """ Called on GET /pull/<version>/ from transport layer
        """
        response = yield self._get_sent_versions(version)
        data = self._wrap_data(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        """ Called on GET /pdu/<pdu_origin>/<pdu_id>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        response = yield self.data_layer.on_data_request(pdu_origin, pdu_id)
        data = self._wrap_data([response])
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_context_metadata_request(self, context):
        """ Called on GET /metadata/<context>/ from transport layer
            Returns a deferred tuple of (code, response)
        """
        response = yield self.data_layer.on_get_metadata(context)
        data = self._wrap_data(response)
        defer.returnValue((200, data))

    @defer.inlineCallbacks
    def on_transport_data(self, transport_data):
        """ Called on PUT /send/<transaction_id> from transport layer
        """
        transaction_id = transport_data.transaction_id

        # Check to see if we a) have a transaction_id associated with this
        # request and if so b) have we already responded to it?
        if transaction_id:
            transaction_results = yield Transaction.findBy(
                txid=transaction_id, origin=transport_data.origin
            )

            if transaction_results:
                # We know about this transaction. Have we responded?
                for t in transaction_results:
                    if t.response_code > 0 and t.response:
                        defer.returnValue(
                            (t.response_code, t.response)
                        )
                        return

        transaction = Transaction.from_transport_data(
                transport_data
            )

        # Pass request to transaction layer.
        try:
            code, response = yield self.data_layer.on_received_transaction(
                    transaction
                )

            transaction.response = response
            transaction.respone_code = code

            yield transaction.save()
        except Exception as e:
            logging.exception(e)

            # transaction.response = {"error": "Internal server error"}
            # transaction.respone_code = 500

            # yield transaction.save()

            defer.returnValue((500, {"error": "Internal server error"}))
            return

        defer.returnValue((transaction.respone_code, transaction.response))

    def trigger_get_context_metadata(self, destination, context):
        """ Try and get the remote home server to give us all metadata about
            a given context
        """
        return self.transport_layer.trigger_get_context_metadata(
            destination, context)

    def trigger_get_pdu(self, destination, pdu_origin, pdu_id):
        return self.transport_layer.trigger_get_data(
            destination, pdu_origin, pdu_id)
