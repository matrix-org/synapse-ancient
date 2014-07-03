# -*- coding: utf-8 -*-
""" Defines various classes to represent the common protocol units used by the
server to server protocol.
"""

from twisted.internet import defer
from ..persistence.transactions import (
    TransactionQueries, PduQueries,
    StateQueries, run_interaction
)

from ..persistence.tables import ReceivedTransactionsTable

import copy
import logging
import json
import time


logger = logging.getLogger("synapse.protocol.units")


class JsonEncodedObject(object):
    """ A common base class for the protocol units. Handles encoding and
    decoding them as JSON.

    This is useful when we are sending json data backwards and forwards,
    and we want a nice way to encode/decode them.

    Attributes:
        unrecognized_keys (dict): A dict containing all the key/value pairs we
            don't recognize.
    """

    valid_keys = []  # keys we will store
    """A list of strings that represent keys we know about
    and can handle. If we have values for these keys they will be
    included in the __dict__ of the class.
    """

    internal_keys = []  # keys to ignore while building dict
    """ A list of strings that should *not* be encoded into JSON.
    """

    def __init__(self, **kwargs):
        """ Takes the dict of `kwargs` and loads all keys that are *valid*
        (i.e., are included in the `valid_keys` list) into the class's
        `__dict__`.

        Any keys that aren't recognized are added to the `unrecognized_keys`
        attribute.

        Args:
            **kwargs: Attributes associated with this protocol unit.
        """
        self.unrecognized_keys = {}  # Keys we were given not listed as valid
        for k, v in kwargs.items():
            if k in self.valid_keys:
                self.__dict__[k] = v
            else:
                self.unrecognized_keys[k] = v

    def get_dict(self):
        """ Converts this protocol unit into a dict, ready to be encoded
        as json

        Returns
            dict
        """
        d = copy.deepcopy(self.__dict__)
        d = {
            k: _encode(v) for (k, v) in d.items()
            if k not in self.internal_keys
        }

        if "unrecognized_keys" in d:
            del d["unrecognized_keys"]
            if self.unrecognized_keys:
                d.update(self.unrecognized_keys)

        return d


class Transaction(JsonEncodedObject):
    """ A transaction is a list of Pdus to be sent to a remote home
        server with some extra metadata.
    """

    valid_keys = [
        "transaction_id",
        "origin",
        "destination",
        "ts",
        "previous_ids",
        "pdus",  # This get's converted to a list of Pdu's
    ]

    internal_keys = [
        "transaction_id",
        "destination",
    ]

    # HACK to get unique tx id
    _next_transaction_id = int(time.time() * 1000)

    def __init__(self, transaction_id=None, pdus=[], **kwargs):
        """ If we include a list of pdus then we decode then as PDU's
        automatically.
        """

        super(Transaction, self).__init__(
            transaction_id=transaction_id,
            pdus=pdus,
            **kwargs
        )

        if self.transaction_id:
            for p in self.pdus:
                p.transaction_id = p

    @staticmethod
    def decode(transaction_dict, outlier=False):
        """ Used to convert a dict from the interwebs to a Transaction
            object. It converts the Pdu dicts into Pdu objects too!
        """
        pdus = [Pdu(outlier=outlier, **p)
                for p in transaction_dict.setdefault("pdus", [])]
        transaction_dict.update(pdus=pdus)

        return Transaction(**transaction_dict)

    @staticmethod
    def create_new(**kwargs):
        """ Used to create a new transaction. Will auto fill out
            transaction_id and ts keys.
        """
        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)
        if "transaction_id" not in kwargs:
            kwargs["transaction_id"] = Transaction._next_transaction_id
            Transaction._next_transaction_id += 1

        return Transaction(**kwargs)

    def have_responded(self):
        """ Have we responded to this transaction?

        Returns:
            Deferred: The result of the deferred is None if we have *not*
            already responded to the transaction (or this is a fake
            transaction without a transaction_id), or a tuple of the form
            `(response_code, response)`, where `response` is a dict which will
            be used as the json response body.
        """
        if not self.transaction_id:
            # This is a fake transaction, which we always process.
            return defer.succeed(None)

        return run_interaction(
            TransactionQueries.get_response_for_received,
            self.transaction_id, self.origin
        )

    def set_response(self, code, response):
        """ Set's how we responded to this transaction. This only makes sense
        for actual transactions with transaction_ids, rather than transactions
        generated from http responses.

        Args:
            code (int): The HTTP status code we returned
            response (dict): The un-json-encoded response body we returned.

        Returns:
            Deferred: Succeeds after we successfully persist the response.
        """
        if not self.transaction_id:
            # This is a fake transaction, which we can't respond to.
            return defer.succeed(None)

        return run_interaction(
            TransactionQueries.set_recieved_txn_response,
            self.transaction_id,
            self.origin,
            code,
            json.dumps(response)
        )

    def persist_as_received(self, response_code, response_json):
        """ Saves this transaction into the received transactions table.

        Args:
            response_code (int): The HTTP response code we responded with.
            response_json (dict): The response body we returned

        Response:
            Deferred: Succeeds after we successfully persist.
        """

        return run_interaction(
            TransactionQueries.insert_received,
            ReceivedTransactionsTable.EntryType(
                transaction_id=self.transaction_id,
                origin=self.origin,
                ts=self.ts,
                response_code=response_code,
                response_json=json.dumps(response_json)
            ),
            self.previous_ids
        )

    @defer.inlineCallbacks
    def prepare_to_send(self):
        """ Prepares this transaction for sending. Persists the transaction and
        computes the correct value for the prev_ids list.

        Returns:
            Deferred: Succeeds when the transaction is ready for transmission.
        """

        self.prev_ids = yield run_interaction(
            TransactionQueries.prep_send_transaction,
            self.transaction_id,
            self.destination,
            self.ts,
            [(p.pdu_id, p.origin) for p in self.pdus]
        )

    def delivered(self, response_code, response_json):
        """ Marks this outgoing transaction as delivered.

        Args:
            response_code (int): The HTTP response code we recieved.
            response_json (dict): The response body.

        Returns:
            Deferred: Succeeds after we persisted the result
        """
        return run_interaction(
            TransactionQueries.delivered_txn,
            self.transaction_id,
            self.destination,
            response_code,
            json.dumps(response_json)
        )


class Pdu(JsonEncodedObject):
    """ A Pdu represents a piece of data sent from a server and is associated
    with a context.

    A Pdu can be classified as "state". For a given context, we can efficiently
    retrieve all state pdu's that haven't been clobbered. Clobbering is done
    via a unique constraint on the tuple (context, pdu_type, state_key). A pdu
    is a state pdu if `is_state` is True.
    """

    valid_keys = [
        "pdu_id",
        "context",
        "origin",
        "ts",
        "pdu_type",
        "is_state",
        "state_key",
        "destinations",
        "transaction_id",
        "prev_pdus",
        "depth",
        "content",
        "outlier",
        "power_level",
        "prev_state_id",
        "prev_state_origin",
    ]

    internal_keys = [
        "destinations",
        "transaction_id",
        "outlier",
    ]

    """ A list of keys that we persist in the database. The column names are
    the same
    """

    # HACK to get unique tx id
    _next_pdu_id = int(time.time() * 1000)

    # TODO: We need to make this properly load content rather than
    # just leaving it as a dict. (OR DO WE?!)

    def __init__(self, destinations=[], is_state=False, prev_pdus=[],
                 outlier=False, **kwargs):
        super(Pdu, self).__init__(
            destinations=destinations,
            is_state=is_state,
            prev_pdus=prev_pdus,
            outlier=outlier,
            **kwargs
        )

    @staticmethod
    def create_new(**kwargs):
        """ Used to create a new pdu. Will auto fill out pdu_id and ts keys.

        Returns:
            Pdu
        """
        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)

        if "pdu_id" not in kwargs:
            kwargs["pdu_id"] = Pdu._next_pdu_id
            Pdu._next_pdu_id += 1

        return Pdu(**kwargs)

    @staticmethod
    @defer.inlineCallbacks
    def current_state(context):
        """ Get a list of PDUs representing the current state of a context.

        Args:
            context (str): The context we're interested in.

        Returns:
            Deferred: Results in a `list` of Pdus
        """

        results = yield run_interaction(
            PduQueries.get_current_state,
            context
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    @classmethod
    def _from_pdu_tuple(cls, pdu_tuple):
        """ Converts a PduTuple to a Pdu

        Args:
            pdu_tuple (synapse.persistence.transactions.PduTuple): The tuple to
                convert

        Returns:
            Pdu
        """
        if pdu_tuple:
            d = copy.copy(pdu_tuple.pdu_entry._asdict())

            if pdu_tuple.state_entry:
                s = copy.copy(pdu_tuple.state_entry._asdict())
                d.update(s)
                d["is_state"] = True

            d["content"] = json.loads(d["content_json"])
            del d["content_json"]

            args = {f: d[f] for f in cls.valid_keys if f in d}
            if "unrecognized_keys" in d and d["unrecognized_keys"]:
                args.update(json.loads(d["unrecognized_keys"]))

            return Pdu(
                prev_pdus=pdu_tuple.prev_pdu_list,
                **args
            )
        else:
            return None

    @staticmethod
    @defer.inlineCallbacks
    def get_persisted_pdu(pdu_id, pdu_origin):
        """ Get's a specific PDU from the database.

        Args:
            pdu_id (str): The PDU ID.
            pdu_origin (str): The PDU origin.

        Retruns:
            Deferred: Results in a Pdu
        """
        pdu_tuple = yield run_interaction(
            PduQueries.get_pdu,
            pdu_id, pdu_origin
        )

        defer.returnValue(Pdu._from_pdu_tuple(pdu_tuple))

    def persist_received(self):
        """ Store this PDU we received in the database.

        Args:
            is_out_of_order (bool):

        Returns:
            Deferred
        """

        return self._persist()

    @defer.inlineCallbacks
    def persist_outgoing(self):
        """ Store this PDU we are sending in the database.

        Returns:
            Deferred
        """

        ret = yield self._persist()

        # This is safe to do since if *we* are sending something, then we must
        # have seen everything we reference (hopefully).
        if self.is_state:
            yield run_interaction(
                StateQueries.handle_new_state,
                self
            )

        defer.returnValue(ret)

    def mark_as_processed(self):
        """ Mark this Pdu as having been processed.

        Returns:
            Deferred
        """
        return run_interaction(
            PduQueries.mark_as_processed,
            self.pdu_id, self.origin
        )

    @defer.inlineCallbacks
    def _persist(self):
        kwargs = copy.copy(self.__dict__)
        del kwargs["content"]
        kwargs["content_json"] = json.dumps(self.content)
        kwargs["unrecognized_keys"] = json.dumps(kwargs["unrecognized_keys"])

        logger.debug("Persisting: %s", repr(kwargs))

        if self.is_state:
            ret = yield run_interaction(
                PduQueries.insert_state,
                **kwargs
            )
        else:
            ret = yield run_interaction(
                PduQueries.insert,
                **kwargs
            )

        yield run_interaction(
            PduQueries.update_min_depth,
            self.context, self.depth
        )

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def populate_previous_pdus(self):
        """ Populates the prev_pdus field with the current most recent pdus.
        This is used when we are creating new Pdus for a context.

        Also populates the `versions` field with the correct value.

        Also populates prev_state_* for state_pdus.

        Returns:
            Deferred: Succeeds when prev_pdus have been successfully updated.
        """

        results = yield run_interaction(
            PduQueries.get_prev_pdus,
            self.context
        )

        self.prev_pdus = [(p_id, origin) for p_id, origin, _ in results]

        vs = [int(v) for _, _, v in results]
        if vs:
            self.depth = max(vs) + 1
        else:
            self.depth = 0

        if self.is_state:
            curr = yield run_interaction(
                StateQueries.current_state,
                self.context,
                self.pdu_type, self.state_key)

            if curr:
                self.prev_state_id = curr.pdu_id
                self.prev_state_origin = curr.origin
            else:
                self.prev_state_id = None
                self.prev_state_origin = None

    @staticmethod
    @defer.inlineCallbacks
    def after_transaction(transaction_id, destination, origin):
        """ Get's a list of PDUs that we sent to a given destination after
        a transaction_id.

        Args:
            transaction_id (str): The transaction_id of the last transaction
                they saw.
            destination (str): The remote home server address.
            origin (str): The local home server address.

        Results:
            Deferred: A list of Pdus.
        """
        results = yield run_interaction(
            PduQueries.get_after_transaction,
            transaction_id,
            destination,
            origin
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    @staticmethod
    @defer.inlineCallbacks
    def paginate(context, pdu_list, limit):
        results = yield run_interaction(
            PduQueries.paginate,
            context, pdu_list, limit
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    def is_new(self):
        return run_interaction(
            PduQueries.is_new,
            pdu_id=self.pdu_id,
            origin=self.origin,
            context=self.context,
            depth=self.depth
        )


def _encode(obj):
    if type(obj) is list:
        return [_encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj
