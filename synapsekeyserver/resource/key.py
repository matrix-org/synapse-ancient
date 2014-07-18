# -*- coding: utf-8 -*-

from twisted.web.resource import Resource
from synapsekeyserver.util.base64util import encode_base64
from synapsekeyserver.util.jsonutil import (
    encode_canonical_json,
    respond_with_json_bytes,
)
from synapsekeyserver.util.signing import sign_json
from OpenSSL import crypto


class LocalKey(Resource):
    isLeaf = True

    def __init__(self, config):
        self.tls_certificate = config.tls_certificate
        self.signing_key = config.signing_key
        self.server_name = config.server_name
        self.response_body = encode_canonical_json(self.response_json_object())

    def response_json_object(self):
        verify_key_bytes = self.signing_key.verify_key.encode()
        x509_certificate_bytes = crypto.dump_certificate(
            crypto.FILETYPE_ASN1,
            self.tls_certificate
        )
        json_object = {
            "server_name": self.server_name,
            "signature_verify_key": encode_base64(verify_key_bytes),
            "tls_certiicate": encode_base64(x509_certificate_bytes)
        }
        signed_json = sign_json(
            json_object,
            self.server_name,
            self.signing_key
        )
        return signed_json

    def getChild(self, name, request):
        if name == '':
            return self
        return super(LocalKey, self).getChild(self, name, request)

    def render_GET(self, request):
        return respond_with_json_bytes(request, 200, self.response_body)
