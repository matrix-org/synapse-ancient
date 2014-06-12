# -*- coding: utf-8 -*-

from twisted.internet import defer

from ..persistence.transaction import TransactionDbEntry
from ..persistence.pdu import (PduDbEntry, PduDestinationEntry,
    PduContextEdgesEntry, PduState, get_pdus_after_transaction_id,
    get_state_pdus_for_context)

import copy
import json
import time


class JsonEncodedObject(object):
    """ Given a list of "valid keys", load them from kwargs into __dict__,
        all unrecognized keys get dumped into an "unrecognized_keys" dict.

        get_dict() returns everything supplied in **kwargs in __init__,
        excluding those listed in "internal_keys"

        This is useful when we are sending json data backwards and forwards,
        and we want a nice way to encode/decode them.
    """

    valid_keys = []  # keys we will store
    internal_keys = []  # keys to ignore while building dict

    def __init__(self, **kwargs):
        self.unrecognized_keys = {}  # Keys we were given not listed as valid
        for k, v in kwargs.items():
            if k in self.valid_keys:
                self.__dict__[k] = v
            else:
                self.unrecognized_keys[k] = v

    def get_dict(self):
        d = copy.deepcopy(self.__dict__)
        d = {k: encode(v) for (k, v) in d.items()
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

    internal_keys = [
            "transaction_id",
            "destination"
        ]

    # HACK to get unique tx id
    _next_transaction_id = int(time.time() * 1000)

    def __init__(self, **kwargs):
        if "transaction_id" not in kwargs:
            kwargs["transaction_id"] = None

        super(Transaction, self).__init__(**kwargs)

        if self.transaction_id:
            for p in self.pdus:
                p.transaction_id = p

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

    def get_db_entry(self):
        return TransactionDbEntry.findOrCreate(
                **{
                    k: v for k, v in self.get_dict().items()
                        if k in self.db_cols
                }
            )


class Pdu(JsonEncodedObject):
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
        """ Used to create a new pdu. Will auto fill out
            pdu_id and ts keys.
        """
        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)

        if "pdu_id" not in kwargs:
            kwargs["pdu_id"] = Pdu._next_pdu_id
            Pdu._next_pdu_id += 1

        return Pdu(**kwargs)

    def get_db_entry(self):
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
        pdus = []
        for db_entry in db_entries:
            d = {k: v for k, v in db_entry.dict().items()
                    if k in Pdu.valid_keys}
            d["content"] = json.loads(db_entry.content_json)
            pdus.append(Pdu(**d))

        yield defer.DeferredList([p.get_destinations_from_db() for p in pdus])
        yield defer.DeferredList([p.get_previous_pdus_from_db() for p in pdus])

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def get_destinations_from_db(self):
        results = yield PduDestinationEntry.findBy(
                pdu_id=self.pdu_id,
                origin=self.origin
            )

        self.destinations = [r.destination for r in results]

    @defer.inlineCallbacks
    def get_previous_pdus_from_db(self):
        results = yield PduContextEdgesEntry.findBy(
                pdu_id=self.pdu_id,
                origin=self.origin
            )

        self.previous_pdus = [{"pdu_id": r.prev_pdu_id, "origin": r.prev_origin}
                    for r in results]

    @defer.inlineCallbacks
    def persist(self):
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
            dl.append(pde.save())

        yield defer.DeferredList(dl, fireOnOneErrback=True)

    @staticmethod
    @defer.inlineCallbacks
    def after_transaction(origin, transaction_id, destination):
        db_entries = yield get_pdus_after_transaction_id(origin, transaction_id,
                destination)

        res = yield Pdu.from_db_entries(db_entries)
        defer.returnValue(res)

    @staticmethod
    @defer.inlineCallbacks
    def get_state(context):
        db_entries = yield get_state_pdus_for_context(context)

        r = yield Pdu.from_db_entries(db_entries)

        defer.returnValue(r)


class Content(object):
    pass


def encode(obj):
    if type(obj) is list:
        return [encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj