# -*- coding: utf-8 -*-

from twistar.dbobject import DBObject
from twisted.internet import defer

import json


class TransactionDbEntry(DBObject):
    TABLENAME = "transactions"  # Table name

    @defer.inlineCallbacks
    def have_responded(self):
        """ Have we responded to this transaction before? If so return
            (response code, response_dict) tuple, else None
        """
        yield self.refresh()

        if self.response_code > 0 and self.response:
            defer.returnValue(
                (self.response_code, json.loads(self.response))
            )

        else:
            defer.returnValue(None)

    def set_response(self, code, repsonse):
        """ Mark this transaction as having been responded to
        """

        self.response = json.dumps(repsonse)
        self.response_code = code

        return self.save()


class LastSentTransactionDbEntry(DBObject):
    TABLENAME = "last_sent_transaction"  # Table name


class TransactionToPduDbEntry(DBObject):
    TABLENAME = "transaction_id_to_pdu"  # Table name
