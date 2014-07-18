# -*- coding: utf-8 -*-

from twisted.internet import reactor, ssl
from twisted.web import server
from twisted.python.log import PythonLoggingObserver

from synapsekeyserver.util.base64util import decode_base64
from synapsekeyserver.resource.key import LocalKey
from synapsekeyserver.config import load_config

from OpenSSL import crypto, SSL

import logging
import nacl.signing
import sys


class KeyServerSSLContextFactory(ssl.ContextFactory):

    def __init__(self, tls_certificate, tls_private_key):
        self._context = SSL.Context(SSL.SSLv23_METHOD)
        self.configure_context(self._context, tls_certificate, tls_private_key)

    @staticmethod
    def configure_context(context, tls_certificate, tls_private_key):
        context.set_options(SSL.OP_NO_SSLv2 | SSL.OP_NO_SSLv3)
        context.use_certificate(tls_certificate)
        context.use_privatekey(tls_private_key)

    def getContext(self):
        return self._context


class KeyServer(object):

    def __init__(self, server_name, tls_certificate_path, tls_private_key_path,
                 signing_key_path, bind_host, bind_port):
        self.server_name = server_name
        self.tls_certificate = self.read_tls_certificate(tls_certificate_path)
        self.tls_private_key = self.read_tls_private_key(tls_private_key_path)
        self.signing_key = self.read_signing_key(signing_key_path)
        self.bind_host = bind_host
        self.bind_port = int(bind_port)

    @staticmethod
    def read_tls_certificate(cert_path):
        with open(cert_path) as cert_file:
            cert_pem = cert_file.read()
            return crypto.load_certificate(crypto.FILETYPE_PEM, cert_pem)

    @staticmethod
    def read_tls_private_key(private_key_path):
        with open(private_key_path) as private_key_file:
            private_key_pem = private_key_file.read()
            return crypto.load_privatekey(crypto.FILETYPE_PEM, private_key_pem)

    @staticmethod
    def read_signing_key(signing_key_path):
        with open(signing_key_path) as signing_key_file:
            signing_key_b64 = signing_key_file.read()
            signing_key_bytes = decode_base64(signing_key_b64)
            return nacl.signing.SigningKey(signing_key_bytes)

    def run(self):
        site = server.Site(LocalKey(self))
        reactor.listenSSL(
            self.bind_port,
            site,
            KeyServerSSLContextFactory(
                self.tls_certificate,
                self.tls_private_key
            ),
            interface=self.bind_host
        )

        logging.basicConfig(level=logging.DEBUG)
        observer = PythonLoggingObserver()
        observer.start()

        reactor.run()


def main():
    key_server = KeyServer(**load_config(__doc__, sys.argv[1:]))
    key_server.run()


if __name__ == "__main__":
    main()