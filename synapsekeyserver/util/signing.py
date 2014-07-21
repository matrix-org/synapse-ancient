# -*- coding: utf-8 -*-
from synapsekeyserver.util.jsonutil import encode_canonical_json
from synapsekeyserver.util.base64util import encode_base64, decode_base64


def sign_json(json_object, signature_name, signing_key):
    signatures = json_object.get("signatures", None)
    if signatures is None:
        signatures = {}

    json_object["signatures"] = {}

    signed = signing_key.sign(encode_canonical_json(json_object))

    signatures[signature_name] = encode_base64(signed.signature)

    json_object["signatures"] = signatures

    return json_object


class InvalidSignature(Exception):
    pass


def verify_signed_json(json_object, signature_name, verify_key):

    signatures = json_object.get("signatures", {})

    try:
        signature_b64 = signatures[signature_name]
    except:
        raise InvalidSignature("Missing signature for %s" % signature_name)

    if len(signature_b64) != 86:
        raise InvalidSignature(
            "Incorrect signature length for %s" % signature_name)

    try:
        signature = decode_base64(signature_b64)
    except:
        raise InvalidSignature(
            "Invalid signature base64 for %s" % signature_name)

    json_object["signatures"] = {}
    message = encode_canonical_json(json_object)

    try:
        verify_key.verify(message, signature)
    except:
        raise InvalidSignature(
            "Forged or corrupt signature for %s " % signature_name)
