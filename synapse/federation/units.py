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


def _encode(obj):
    if type(obj) is list:
        return [_encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj
