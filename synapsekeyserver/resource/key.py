# -*- coding: utf-8 -*-

from twisted.web.resource import Resource
from twisted.web.server import NOT_DONE_YET
from twisted.internet import defer
from synapsekeyserver.util.base64util import encode_base64, decode_base64
from synapsekeyserver.util.jsonutil import (
    encode_canonical_json,
    respond_with_json_bytes,
    respond_with_json_object,
)
from synapsekeyserver.keyclient import fetch_server_key
from synapsekeyserver.util.signing import sign_json, verify_signed_json
from OpenSSL import crypto
from nacl.signing import VerifyKey
import logging


logger = logging.getLogger(__name__)


class LocalKey(Resource):

    def __init__(self, config):
        self.config = config
        self.response_body = encode_canonical_json(
            self.response_json_object(config)
        )
        Resource.__init__(self)

    @staticmethod
    def response_json_object(config):
        verify_key_bytes = config.signing_key.verify_key.encode()
        x509_certificate_bytes = crypto.dump_certificate(
            crypto.FILETYPE_ASN1,
            config.tls_certificate
        )
        json_object = {
            u"server_name": config.server_name,
            u"signature_verify_key": encode_base64(verify_key_bytes),
            u"tls_certificate": encode_base64(x509_certificate_bytes)
        }
        signed_json = sign_json(
            json_object,
            config.server_name,
            config.signing_key
        )
        return signed_json

    def getChild(self, name, request):
        logger.info("getChild %s %s", name, request)
        if name == '':
            return self
        else:
            return RemoteKey(name, self.config)

    def render_GET(self, request):
        return respond_with_json_bytes(request, 200, self.response_body)


class RemoteKey(Resource):
    isLeaf = True

    def __init__(self, server_name, config):
        self.server_name = server_name
        self.config = config

    def render_GET(self, request):
        self._async_render_GET(request)
        return NOT_DONE_YET

    @defer.inlineCallbacks
    def _async_render_GET(self, request):
        try:
            server_keys, certificate = yield fetch_server_key(
                self.server_name,
                self.config.ssl_context_factory
            )

            resp_server_name = server_keys[u"server_name"]
            verify_key_b64 = server_keys[u"signature_verify_key"]
            tls_certificate_b64 = server_keys[u"tls_certificate"]
            verify_key = VerifyKey(decode_base64(verify_key_b64))

            if resp_server_name != self.server_name:
                raise ValueError("Wrong server name '%s' != '%s'"
                        % (resp_server_name, self.server_name))

            x509_certificate_bytes = crypto.dump_certificate(
                crypto.FILETYPE_ASN1,
                certificate
            )

            if encode_base64(x509_certificate_bytes) != tls_certificate_b64:
                raise ValueError("TLS certificate doesn't match")

            verify_signed_json(server_keys, self.server_name, verify_key)

            signed_json = sign_json(
                server_keys,
                self.config.server_name,
                self.config.signing_key
            )

            respond_with_json_object(request, 200, signed_json)
        except Exception as e:
            respond_with_json_object(request, 502, {
                u"error": {u"code": 502, u"message": e.message}
            })
