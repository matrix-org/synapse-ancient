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

    def send_pdu(self, destinations, pdu_json, order):
        """ Schedules the pdu_json to be sent to the given destination.

            The order is an integer which defines the order in which pdus
            will be sent (ones with a larger order come later). This is to
            make sure we maintain the ordering defined by the versions without
            having to know what the versions look like at this layer.

            Returns a deferred list
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

    def send(self, transaction_layer):
        """ Sends the transaction via the given transaction_layer
        """
        transaction_layer.send_transaction(self)

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


class _PendingPdus(DBObject):
    """ Stores pdus that are waiting to be sent to a given destination.

        Items get removed from this table once they have been convereted
        into a Transaction
    """

    TABLENAME = "pending_pdus"  # Table name


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

        self.pending_transactions = {}
        self.pending_pdus = {}

    def set_data_layer(self, data_layer):
        self.data_layer = data_layer

    @defer.inlineCallbacks
    def send_pdu(self, destinations, pdu_json):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferredList
        """
        pass

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

    @defer.inlineCallbacks
    def _send_transaction(self, transaction):
        code, response = yield self.transport_layer.send_data(
                transaction.to_transport_data()
            )

        transaction.respone_code = code
        transaction.response = response

        yield transaction.save()

        defer.returnValue((code, response))

    @defer.inlineCallbacks
    def _send_pdu(self, destination, ts, pdu_json):
        deferred = defer.Deferred()
        if destination in self.pending_transactions:
            pending_pdu = _PendingPdus.create(
                pdu_json=self.dumps(pdu_json),
                destination=destination,
                ts=ts
            )

            saved_deferred = pending_pdu.save()
            self.pending_transactions[destination].addCallback(
                    lambda x: saved_deferred
                )

            yield saved_deferred
        else:
            transaction = Transaction.create(
                    ts=ts,
                    origin=self.server_name,
                    destination=destination,
                    pdu_list=[pdu_json]
                )

            d = transaction.save()

            d.addCallback(
                lambda: self._send_transaction(transaction)
            )

            self.pending_transactions[destination] = d

        self.pending_pdus[pending_pdu.id] = deferred
        response = yield deferred

        defer.returnValue(response)

    def _on_sent(self, destination):
        pass


class _TransactionQueue(object):
    """ This class makes sure we only have one transaction in flight at
        a time for a given destination.

        It batches PDUs into single transactions.
    """

    def __init__(self):
        self.pending_transactions = {}
        self.pending_pdus = {}

    @defer.inlineCallbacks
    def send_pdu(self, destinations, pdu_json):
        """ Schedules the pdu_json to be sent to the given destination.

            Returns a deferredList
        """
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        deferreds = []

        for dest in destinations:
            deferred = defer.Deferred()
            if dest in self.pending_transactions:
                pending_pdu = _PendingPdus.create(
                    pdu_json=self.dumps(pdu_json),
                    destination=dest,
                    ts=int(time.time() * 1000)
                )

                d = pending_pdu.save()

                d.addCallback(
                    lambda: self.pending_pdus.set(pending_pdu.id, deferred)
                )

                self.pending_transactions[dest].addCallback(lambda x: d)
            else:
                transaction = Transaction.create(
                        ts=int(time.time() * 1000),
                        origin=self.server_name,
                        destination=dest,
                        pdu_list=[pdu_json]
                    )

                d = transaction.save()

                d.addCallback(
                    lambda: self._send_transaction(transaction)
                )

                d.addCallback()

                self.pending_transactions[dest] = d

            deferreds.append(deferred)

        return defer.deferredList(deferreds)

    @defer.inlineCallbacks
    def _send_pdu(self, destination, ts, pdu_json):
        deferred = defer.Deferred()
        if destination in self.pending_transactions:
            pending_pdu = _PendingPdus.create(
                pdu_json=self.dumps(pdu_json),
                destination=destination,
                ts=ts
            )

            saved_deferred = pending_pdu.save()
            self.pending_transactions[destination].addCallback(
                    lambda x: saved_deferred
                )

            yield saved_deferred
        else:
            transaction = Transaction.create(
                    ts=ts,
                    origin=self.server_name,
                    destination=destination,
                    pdu_list=[pdu_json]
                )

            d = transaction.save()

            d.addCallback(
                lambda: self._send_transaction(transaction)
            )

            self.pending_transactions[destination] = d

        self.pending_pdus[pending_pdu.id] = deferred
        response = yield deferred

        defer.returnValue(response)

    @defer.inlineCallbacks
    def _send_transaction(self, transaction, deferred_list):
        code, response = yield self.transport_layer.send_data(
                transaction.to_transport_data()
            )

        transaction.respone_code = code
        transaction.response = response

        defer.returnValue((code, response))

        yield transaction.save()

        if len(response) == len(deferred_list):
            for i in range(len(response)):
                deferred_list[i].callback(response[i])

    @defer.inlineCallbacks
    def _send_from_pending_table(self, destination):
        deferred = defer.Deferred()

        if destination in self.pending_transactions:
            return

        self.pending_transactions[destination] = deferred

        rows = yield _PendingPdus.findBy(destination=destination)

        if not rows:
            # Nothing more to send to this server!
            deferred.callback(None)
            return

        transaction = Transaction.create(
                        ts=int(time.time() * 1000),
                        origin=self.server_name,
                        destination=destination,
                        pdu_list=[p.pdu_json for p in rows]
                    )

        deferred_list = [self.pending_pdus[p.id] for p in rows]
        ret = yield self._send_transaction(
            transaction, deferred_list)

        deferred.callback(ret)

        self.pending_transactions[destination]

        self._send_from_pending_table(destination)
