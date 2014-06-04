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

    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            The order is an integer which defines the order in which pdus
            will be sent (ones with a larger order come later). This is to
            make sure we maintain the ordering defined by the versions without
            having to know what the versions look like at this layer.

            pdu_json is a python dict that can be converted into json.

            Returns a deferred which returns when the pdu has successfully
            been sent to the destination.
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

        A transaction wraps a bunch of PDUs that have been received / need to
        be sent to a particular server.

        Stores the "pdu_list" as json, and converts it to
        a json encoded string in "data" before storage.

        When loading from the db, will decode the "data"
        column into "pdu_list"

        Properties:
            - transaction_id
            - ts                     - time we started trying to send this txn
            - destination            - where this txn is going (can be us)
            - origin                 - where this txn has come from (can be us)
            - pdu_list               - a list of pdus the txn contains
            - response_code          - response code for this txn if known
            - response               - the response data
            - (internal: ) data      - the json encoded pdu_list
    """

    TABLENAME = "transactions"  # Table name
    _next_transaction_id = int(time.time())  # XXX Temp. hack to make it unique

    def create(ts, origin, destination, pdu_list):
        """ pdu_list: list of pdu's which have been encoded as dicts
        """
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

    # INTERNAL
    def beforeSave(self):
        # We're about to be saved! Quick update the data!
        self.data = json.dumps(self.pdu_list)
        return True

    # INTERNAL
    def afterInit(self):
        if self.data:
            # We were probably loaded from the db, so decode data
            # into pdu_list
            self.pdu_list = json.loads(self.data)

        return True

    # INTERNAL
    @defer.inlineCallbacks
    def refresh(self):
        ret = yield super(DBObject, self).refresh()

        # Automagically store self.pdu_list as json in data column
        if self.data:
            self.pdu_list = json.loads(self.data)

        defer.returnValue(ret)


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

        # Responsible for batching pdus
        self._transaction_queue = _TransactionQueue(transport_layer)

    def set_data_layer(self, data_layer):
        self.data_layer = data_layer

    @defer.inlineCallbacks
    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferred
        """
        self._transaction_queue.enqueue_pdu(destination, pdu_json, order)

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


class _TransactionQueue(object):
    """ This class makes sure we only have one transaction in flight at
        a time for a given destination.

        It batches pending PDUs into single transactions.
    """

    def __init__(self, transport_layer):

        self.transport_layer = transport_layer

        # Is a mapping from destinations -> deferreds. Used to keep track
        # of which destinations have transactions in flight and when they are
        # done
        self.pending_transactions = {}

        # Is a mapping from destination -> list of
        # tuple(pending pdus, deferred, order)
        self.pending_pdus_list = {}

    @defer.inlineCallbacks
    def enqueue_pdu(self, destination, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferred
        """
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        deferred = defer.Deferred()
        self.pending_pdus_list.setdefault(destination, []).append(
                    (pdu_json, deferred, order)
                )

        self._attempt_new_transaction(destination)

        return deferred

    @defer.inlineCallbacks
    def _attempt_new_transaction(self, destination):
        if destination in self.pending_transactions:
            return

        # tuple_list is a list of (pending_pdu, deferred, order)
        tuple_list = self.pending_pdus_list.get(destination)

        if not tuple_list:
            return

        # Sort based on the order field
        tuple_list.sort(key=lambda t: t[2])

        transaction = Transaction.create(
                        ts=int(time.time() * 1000),
                        origin=self.server_name,
                        destination=destination,
                        pdu_list=[p[0] for p in tuple_list]
                    )

        code, response = yield self.transport_layer.send_data(
                transaction.to_transport_data()
            )

        if code == 200:
            for _, deferred, _ in tuple_list:
                deferred.callback(None)

                # Ensures we don't continue until all callbacks on that
                # deferred have fired
                yield deferred

        # At this point we know the layer above has been notified of all the
        # pdus that have successfully been sent.
        # This means that it safe to mark the transaction as sent. Otherwise
        # if we died between marking the transaction as sent and the layers
        # above persisting this, they would never get told that it was
        # successfully sent.

        transaction.respone_code = code
        transaction.response = response

        defer.returnValue((code, response))

        yield transaction.save()

        del self.pending_transactions[destination]

        # Check to see if there is anything else to send.
        self._attempt_new_transaction(self, destination)