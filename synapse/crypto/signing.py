# -*- coding: utf-8 -*-
from synapse.util.jsonutil import encode_canonical_json
from synapse.util.base64util import encode_base64, decode_base64


def sign_json(json_object, signature_name, signing_key):
    """Sign the JSON object. Stores the signature in json_object["signatures"].

    Args:
        json_object (dict): The JSON object to sign.
        signature_name (str): The name of the signing entity.
        signing_key (nacl.signing.SigningKey): The key to sign the JSON with.

    Returns:
        The modified, signed JSON object."""

    signatures = json_object.get("signatures", None)
    if signatures is None:
        signatures = {}

    json_object["signatures"] = {}

    signed = signing_key.sign(encode_canonical_json(json_object))

    signatures[signature_name] = encode_base64(signed.signature)

    json_object["signatures"] = signatures

    return json_object


class InvalidSignature(Exception):
    """A signature was invalid."""
    pass


def verify_signed_json(json_object, signature_name, verify_key):
    """Check a signature on a signed JSON object.

    Args:
        json_object (dict): The signed JSON object to check.
        signature_name (str): The name of the signature to check.
        verifiy_key (nacl.signing.VerifyKey): The key to verify the signature.

    Raises:
        InvalidSignature: If the signature isn't valid
    """

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
