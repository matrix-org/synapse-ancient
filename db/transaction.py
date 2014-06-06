# -*- coding: utf-8 -*-

from twisted.internet import defer
from twistar.dbobject import DBObject

import json
import time


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

    @staticmethod
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