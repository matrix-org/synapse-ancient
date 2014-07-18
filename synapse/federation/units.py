# -*- coding: utf-8 -*-
""" Defines the JSON structure of the protocol units used by the server to
server protocol.
"""

from twisted.internet import defer
from synapse.persistence.transactions import (
    TransactionQueries, PduQueries,
    StateQueries, run_interaction
)

from synapse.persistence.tables import ReceivedTransactionsTable

import copy
import logging
import json
import time


logger = logging.getLogger(__name__)


class JsonEncodedObject(object):
    """ A common base class for defining protocol units that are represented
    as JSON.

    Attributes:
        unrecognized_keys (dict): A dict containing all the key/value pairs we
            don't recognize.
    """

    valid_keys = []  # keys we will store
    """A list of strings that represent keys we know about
    and can handle. If we have values for these keys they will be
    included in the `dictionary` instance variable.
    """

    internal_keys = []  # keys to ignore while building dict
    """A list of strings that should *not* be encoded into JSON.
    """

    required_keys = []
    """A list of strings that we require to exist. If they are not given upon
    construction it raises an exception.
    """

    def __init__(self, **kwargs):
        """ Takes the dict of `kwargs` and loads all keys that are *valid*
        (i.e., are included in the `valid_keys` list) into the dictionary`
        instance variable.

        Any keys that aren't recognized are added to the `unrecognized_keys`
        attribute.

        Args:
            **kwargs: Attributes associated with this protocol unit.
        """
        self.dictionary = {}
        self.unrecognized_keys = {}  # Keys we were given not listed as valid

        for required_key in self.required_keys:
            if required_key not in kwargs:
                raise RuntimeError("Key %s is required" % required_key)

        for k, v in kwargs.items():
            if k in self.valid_keys:
                self.dictionary[k] = v
            else:
                self.unrecognized_keys[k] = v

    def __getattr__(self, name):
        if name in self.valid_keys and name in self.dictionary:
            return self.dictionary[name]
        else:
            raise AttributeError(name)

    def __setattr__(self, name, value):
        if name in self.valid_keys:
            self.dictionary[name] = value
        else:
            object.__setattr__(self, name, value)

    def get_dict(self):
        """ Converts this protocol unit into a :py:class:`dict`, ready to be
        encoded as JSON.

        The keys it encodes are: `valid_keys` - `internal_keys`

        Returns
            dict
        """
        d = copy.deepcopy(self.dictionary)
        d = {
            k: _encode(v) for (k, v) in d.items()
            if k not in self.internal_keys
        }

        if "unrecognized_keys" in d:
            del d["unrecognized_keys"]
            if self.unrecognized_keys:
                d.update(self.unrecognized_keys)

        return d

    def __str__(self):
        return "(%s, %s, %s)" % (
            self.__class__.__name__,
            repr(self.dictionary),
            repr(self.unrecognized_keys)
        )


class Pdu(JsonEncodedObject):
    """ A Pdu represents a piece of data sent from a server and is associated
    with a context.

    A Pdu can be classified as "state". For a given context, we can efficiently
    retrieve all state pdu's that haven't been clobbered. Clobbering is done
    via a unique constraint on the tuple (context, pdu_type, state_key). A pdu
    is a state pdu if `is_state` is True.

    Example pdu::

        {
            "pdu_id": "78c",
            "ts": 1404835423000,
            "origin": "bar",
            "prev_ids": [
                ["23b", "foo"],
                ["56a", "bar"],
            ],
            "content": { ... },
        }

    """

    valid_keys = [
        "pdu_id",
        "context",
        "origin",
        "ts",
        "pdu_type",
        "destinations",
        "transaction_id",
        "prev_pdus",
        "depth",
        "content",
        "outlier",
        "is_state",  # Below this are keys valid only for State Pdus.
        "state_key",
        "power_level",
        "prev_state_id",
        "prev_state_origin",
    ]

    internal_keys = [
        "destinations",
        "transaction_id",
        "outlier",
    ]

    required_keys = [
        "pdu_id",
        "context",
        "origin",
        "ts",
        "pdu_type",
        "content",
    ]

    # HACK to get unique tx id
    _next_pdu_id = int(time.time() * 1000)

    # TODO: We need to make this properly load content rather than
    # just leaving it as a dict. (OR DO WE?!)

    def __init__(self, destinations=[], is_state=False, prev_pdus=[],
                 outlier=False, **kwargs):
        if is_state:
            for required_key in ["state_key"]:
                if required_key not in kwargs:
                    raise RuntimeError("Key %s is required" % required_key)

        super(Pdu, self).__init__(
            destinations=destinations,
            is_state=is_state,
            prev_pdus=prev_pdus,
            outlier=outlier,
            **kwargs
        )

    @staticmethod
    def create_new(**kwargs):
        """ Used to create a new pdu. Will auto fill out the required `pdu_id`
        and `ts` keys.

        Returns:
            Pdu
        """
        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)

        if "pdu_id" not in kwargs:
            kwargs["pdu_id"] = Pdu._next_pdu_id
            Pdu._next_pdu_id += 1

        return Pdu(**kwargs)

    @classmethod
    def from_pdu_tuple(cls, pdu_tuple):
        """ Converts a PduTuple to a Pdu

        Args:
            pdu_tuple (synapse.persistence.transactions.PduTuple): The tuple to
                convert

        Returns:
            Pdu
        """
        if pdu_tuple:
            d = copy.copy(pdu_tuple.pdu_entry._asdict())

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


class Transaction(JsonEncodedObject):
    """ A transaction is a list of Pdus to be sent to a remote home
    server with some extra metadata.

    Example transaction::

        {
            "origin": "foo",
            "prev_ids": ["abc", "def"],
            "pdus": [
                ...
            ],
        }

    """

    valid_keys = [
        "transaction_id",
        "origin",
        "destination",
        "ts",
        "previous_ids",
        "pdus",
    ]

    internal_keys = [
        "transaction_id",
        "destination",
    ]

    required_keys = [
        "transaction_id",
        "origin",
        "destination",
        "ts",
        "pdus",
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

    @staticmethod
    def create_new(pdus, **kwargs):
        """ Used to create a new transaction. Will auto fill out
        transaction_id and ts keys.
        """
        if "ts" not in kwargs:
            kwargs["ts"] = int(time.time() * 1000)
        if "transaction_id" not in kwargs:
            kwargs["transaction_id"] = Transaction._next_transaction_id
            Transaction._next_transaction_id += 1

        for p in pdus:
            p.transaction_id = kwargs["transaction_id"]

        kwargs["pdus"] = [p.get_dict() for p in pdus]

        return Transaction(**kwargs)


def _encode(obj):
    if type(obj) is list:
        return [_encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj
