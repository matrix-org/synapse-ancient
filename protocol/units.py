# -*- coding: utf-8 -*-

import copy


class JsonEncodedObject(object):

    def __init__(self, **kwargs):
        self.unrecognized_keys = {}
        for k, v in kwargs.items():
            if k in self.valid_keys:
                self.__dict__[k] = v
            else:
                self.unrecognized_keys[k] = v

    def get_dict(self):
        d = copy.deepcopy(self.__dict__)
        d = {k: encode(v) for (k, v) in d.items() if v}

        if "unrecognized_keys" in d:
            del d["unrecognized_keys"]
            if self.unrecognized_keys:
                d.update(self.unrecognized_keys)

        return d


class Transaction(JsonEncodedObject):
    valid_keys = [
            "transaction_id",
            "origin",
            "destination",
            "ts",
            "previous_ids",
            "pdus"  # This get's converted to a list of Pdu's
        ]

    def __init__(self, **kwargs):
        super(Transaction, self).__init__(**kwargs)

        if "pdus" in kwargs:
            self.pdus = [Pdu(**p) for p in self.pdus]


class Pdu(JsonEncodedObject):
    valid_keys = [
            "pdu_id",
            "origin",
            "destinations",
            "ts",
            "pdus",
            "pdu_type",
            "is_state",
            "state_key",
            "destinations",
            "transaction_ids",
            "previous_pdus",
            "content"
        ]


class Content(object):
    pass


def encode(obj):
    if type(obj) is list:
        return [encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj