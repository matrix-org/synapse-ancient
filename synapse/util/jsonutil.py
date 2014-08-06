# -*- coding: utf-8 -*-

import json


def encode_canonical_json(json_object):
    """Encodes the shortest UTF-8 JSON encoding with dictionary keys
    lexicographically sorted by unicode code point.

    Args:
        json_object (dict): The JSON object to encode.

    Returns:
        bytes encoding the JSON object"""

    return json.dumps(
        json_object,
        ensure_ascii=False,
        separators=(',', ':'),
        sort_keys=True
    ).encode("UTF-8")


def encode_pretty_printed_json(json_object):
    """Encodes the JSON object dict as human readable ascii bytes."""

    return json.dumps(
        json_object,
        ensure_ascii=True,
        indent=4,
        sort_keys=True,
    ).encode("ascii")
