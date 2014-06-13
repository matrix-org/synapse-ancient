# -*- coding: utf-8 -*-

from twistar.dbobject import DBObject


class TransactionDbEntry(DBObject):
    TABLENAME = "transactions"  # Table name


class LastSentTransactionDbEntry(DBObject):
    TABLENAME = "last_sent_transaction"  # Table name


class TransactionToPduDbEntry(DBObject):
    TABLENAME = "transaction_id_to_pdu"  # Table name


class TransactionResponses(DBObject):
    TABLENAME = "transaction_responses"  # Table name
