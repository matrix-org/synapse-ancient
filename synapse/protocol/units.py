# -*- coding: utf-8 -*-
""" Defines various classes to represent the common protocol units used by the
server to server protocol.
"""

from twisted.internet import defer

from ..persistence.transaction import TransactionDbEntry, TransactionResponses
from ..persistence.pdu import (PduDbEntry, PduDestinationEntry,
    PduContextEdgesEntry, PduState, get_pdus_after_transaction_id,
    get_state_pdus_for_context)

import copy
import json
import time


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
        d = {k: _encode(v) for (k, v) in d.items()
                        if k not in self.internal_keys}

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
            "pdus"  # This get's converted to a list of Pdu's
        ]

    db_cols = [
        "transaction_id",
        "origin",
        "ts"
    ]
    """ A list of keys that we persist in the database. The column names are
    the same
    """

    internal_keys = [
            "transaction_id",
            "destination"
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

        self._db_entry = None

    @staticmethod
    def decode(transaction_dict):
        """ Used to convert a dict from the interwebs to a Transaction
            object. It converts the Pdu dicts into Pdu objects too!
        """
        pdus = [Pdu(**p) for p in transaction_dict.setdefault("pdus", [])]
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

    def persist(self):
        """ Persists the transaction. This is a no-op for transactions without
        transaction_id, i.e., transactions created from responses to requests.

        Returns:
            Deferred.
        """

        if not self.transaction_id:
            # We only persist transaction's with IDs, rather than "fake" ones
            # generated after we receive a request
            return defer.succeed(None)

        entry = TransactionResponses(
                **{
                    k: v for k, v in self.get_dict().items()
                        if k in self.db_cols
                }
            )

        return entry.save()

    @defer.inlineCallbacks
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
            defer.returnValue(None)
            return

        entry = yield TransactionResponses.findBy(
                transaction_id=self.transaction_id,
                origin=self.origin
            )

        if entry:
            entry = entry[0]  # We know there can only be one
            defer.returnValue(entry.response_code, json.loads(entry.response))
            return

        defer.returnValue(None)

    @defer.inlineCallbacks
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
            defer.returnValue(None)
            return

        entry = TransactionResponses(
                    transaction_id=self.transaction_id,
                    origin=self.origin
                )

        entry.response_code = code
        entry.response = json.dumps(response)

        yield entry.save()


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
            "previous_pdus",
            "content"
        ]

    internal_keys = [
            "destinations",
            "transaction_id"
        ]

    db_cols = [
        "pdu_id",
        "context",
        "origin",
        "ts",
        "pdu_type",
        "is_state",
        "state_key",
        "transaction_id"
    ]
    """ A list of keys that we persist in the database. The column names are
    the same
    """

    # HACK to get unique tx id
    _next_pdu_id = int(time.time() * 1000)

    # TODO: We need to make this properly load content rather than
    # just leaving it as a dict. (OR DO WE?!)

    def __init__(self, destinations=[], is_state=False, **kwargs):
        super(Pdu, self).__init__(
                destinations=destinations,
                is_state=is_state,
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

    def get_db_entry(self):
        """
        Returns:
            synapse.persistence.pdu.PduDbEntry: The DBObject associated with
            this PDU, if one isn't found in the DB, create one (but doesn't
            save it).
        """
        return PduDbEntry.findOrCreate(
                content_json=json.dumps(self.content),
                **{
                    k: v for k, v in self.get_dict().items()
                        if k in self.db_cols
                }
            )

    @staticmethod
    @defer.inlineCallbacks
    def from_db_entries(db_entries):
        """ Converts a list of synapse.persistence.pdu.PduDbEntry to a list
        of Pdu's. This goes and hits the database to load the `previous_pdus`
        and `destinations` keys.

        Args:
            db_entries (list): A lust of synapse.persistence.pdu.PduDbEntry

        Returns:
            Deferred: Results in a list of Pdus.
        """
        pdus = []
        for db_entry in db_entries:
            d = {k: v for k, v in db_entry.dict().items()
                    if k in Pdu.valid_keys}
            d["content"] = json.loads(db_entry.content_json)
            pdus.append(Pdu(**d))

        for p in pdus:
            yield p.get_destinations_from_db()
            yield p.get_previous_pdus_from_db()

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def get_destinations_from_db(self):
        """ Loads the `destinations` key from the db.

        Returns:
            Deferred
        """
        results = yield PduDestinationEntry.findBy(
                pdu_id=self.pdu_id,
                origin=self.origin
            )

        self.destinations = [r.destination for r in results]

    @defer.inlineCallbacks
    def get_previous_pdus_from_db(self):
        """ Loads the `previous_pdus` key from the db.

        Returns:
            Deferred
        """
        results = yield PduContextEdgesEntry.findBy(
                pdu_id=self.pdu_id,
                origin=self.origin
            )

        self.previous_pdus = [{"pdu_id": r.prev_pdu_id, "origin": r.prev_origin}
                    for r in results]

    @defer.inlineCallbacks
    def persist(self):
        """ Persists this Pdu in the database. This writes to seperate tables
        to store the `destinations` and `previous_pdus` attributes.

        Returns:
            Deferred: Succeeds when persistance has been successful.
        """
        # FIXME: This entire thing should be a single transaction.

        db = yield self.get_db_entry()
        yield db.save()

        dl = []

        if self.is_state:
            # We need to persist this as well.
            state = PduState(
                    pdu_row_id=db.id,
                    context=self.context,
                    pdu_type=self.pdu_type,
                    state_key=self.state_key
                )

            dl.append(state.save())

        # Update destinations
        for dest in self.destinations:
            pde = PduDestinationEntry(
                    pdu_id=self.pdu_id,
                    origin=self.origin,
                    destination=dest
                )
            yield pde.save()

    @staticmethod
    @defer.inlineCallbacks
    def after_transaction(origin, transaction_id, destination):
        """ Get all pdus after a transaction_id that originated from a given
        home server.

        Args:
            origin (str): Only returns pdus with this origin.
            transaction_id (str): The transaction_id to get PDU's after. Not
                inclusive.
            destination (str): The home server that received the transacion.

        Returns:
            Deferred: Results in a list of PDUs that were sent after the
            given transaction.
        """
        db_entries = yield get_pdus_after_transaction_id(origin, transaction_id,
                destination)

        res = yield Pdu.from_db_entries(db_entries)
        defer.returnValue(res)

    @staticmethod
    @defer.inlineCallbacks
    def get_state(context):
        """ Get all PDU's associated with a given context.

        Args:
            context (str): The context to get state for.

        Returns:
            Deferred: Results in a list of PDUs that represent the current
            state of the contex.t
        """
        db_entries = yield get_state_pdus_for_context(context)

        r = yield Pdu.from_db_entries(db_entries)

        defer.returnValue(r)


def _encode(obj):
    if type(obj) is list:
        return [_encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj