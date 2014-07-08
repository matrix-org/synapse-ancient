# -*- coding: utf-8 -*-
""" Defines various classes to represent the common protocol units used by the
server to server protocol.
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
    """ A common base class for the protocol units Handles encoding and
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
    """A list of strings that should *not* be encoded into JSON.
    """

    required_keys = []
    """A list of strings that we require to exist. If they are not given upon
    construction it raises an exception.
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
        for required_key in self.required_keys:
            if required_key not in kwargs:
                raise RuntimeError("Key %s is required" % required_key)

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

    required_keys = [
        "pdu_id",
        "context",
        "origin",
        "ts",
        "pdu_type",
        "content",
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
