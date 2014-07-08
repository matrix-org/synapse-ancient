# -*- coding: utf-8 -*-

from twisted.internet import defer

from .units import JsonEncodedObject

from synapse.persistence.transactions import (
    TransactionQueries, PduQueries, StateQueries, run_interaction
)

import copy
import json
import logging
import time

logger = logging.getLogger(__name__)


class ReplicationLayer(object):

    def __init__(self, server_name, transport_layer):
        self.server_name = server_name

        self.transport_layer = transport_layer
        self.transport_layer.register_received_callbacks(self)
        self.transport_layer.register_request_callbacks(self)

        self._transaction_queue = _TransactionQueue(
            server_name,
            transport_layer
        )

        self.handler = None

        self._order = 0

    def set_handler(self, handler):
        self.handler = handler

    @defer.inlineCallbacks
    def send_pdu(self, pdu):
        order = self._order
        self._order += 1

        logger.debug("[%s] Persisting PDU", pdu.pdu_id)

        yield pdu.populate_previous_pdus()

        # Save *before* trying to send
        yield pdu.persist_outgoing()

        logger.debug("[%s] Persisted PDU", pdu.pdu_id)
        logger.debug("[%s] transaction_layer.enqueue_pdu... ", pdu.pdu_id)

        yield self._transaction_queue.enqueue_pdu(pdu, order)

        logger.debug("[%s] transaction_layer.enqueue_pdu... done", pdu.pdu_id)

    @defer.inlineCallbacks
    def paginate(self, dest, context, limit):
        logger.debug("paginate context=%s, dest=%s", context, dest)
        extremities = yield run_interaction(
            PduQueries.get_back_extremities,
            context
        )

        logger.debug("paginate extrem=%s", extremities)

        if not extremities:
            return

        transaction_data = yield self.transport_layer.trigger_paginate(
            dest, context, extremities, limit)

        logger.debug("paginate transaction_data=%s", repr(transaction_data))

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=False, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def get_pdu(self, destination, pdu_origin, pdu_id, outlier=False):
        logger.debug("get_pdu dest=%s, pdu_origin=%s, pdu_id=%s",
                     destination, pdu_origin, pdu_id)

        transaction_data = yield self.transport_layer.trigger_get_pdu(
            destination, pdu_origin, pdu_id)

        transaction = Transaction(**transaction_data)

        pdu_list = [Pdu(outlier=outlier, **p) for p in transaction.pdus]

        pdu = None
        if pdu_list:
            pdu = pdu_list[0]
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdu)

    @defer.inlineCallbacks
    def get_state_for_context(self, destination, context):
        logger.debug(
            "get_state_for_context context=%s, dest=%s", context, destination)

        transaction_data = yield self.transport_layer.trigger_get_context_state(
            destination, context)

        transaction = Transaction(**transaction_data)

        pdus = [Pdu(outlier=True, **p) for p in transaction.pdus]
        for pdu in pdus:
            yield self._handle_new_pdu(pdu)

        defer.returnValue(pdus)

    @defer.inlineCallbacks
    def on_paginate_request(self, context, versions, limit):
        logger.debug(
            "on_paginate_request context=%s", context)

        pdus = yield Pdu.paginate(context, versions, limit)

        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_transaction(self, transaction_data):
        transaction = Transaction(**transaction_data)

        logger.debug("[%s] Got transaction", transaction.transaction_id)

        response = yield transaction.have_responded()

        if response:
            logger.debug("[%s] We've already responed to this request",
                         transaction.transaction_id)
            defer.returnValue(response)
            return

        logger.debug("[%s] Transacition is new", transaction.transaction_id)

        try:
            pdu_list = [Pdu(**p) for p in transaction.pdus]

            dl = []
            for pdu in pdu_list:
                dl.append(self._handle_new_pdu(pdu))

            results = yield defer.DeferredList(dl)

            ret = []
            for r in results:
                if r[0]:
                    ret.append({})
                else:
                    logger.exception(r[1])
                    ret.append({"error": str(r[1])})

            logger.debug("Returning: %s", str(ret))

            yield transaction.set_response(200, response)
            defer.returnValue((200, response))
        except Exception as e:
            logger.exception(e)

            # We don't save a 500 response!

            defer.returnValue((500, {"error": "Internal server error"}))
            return

    @defer.inlineCallbacks
    def on_context_state_request(self, context):
        logger.debug("on_context_state_request context=%s", context)
        pdus = yield Pdu.current_state(context)
        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_pdu_request(self, pdu_origin, pdu_id):
        logger.debug(
            "on_pdu_request pdu_origin=%s, pdu_id=%s", pdu_origin, pdu_id)

        pdu = yield Pdu.get_persisted_pdu(pdu_id, pdu_origin)

        pdus = []
        if not pdu:
            pdus = [pdu]

        defer.returnValue((200, self._wrap_pdus(pdus)))

    @defer.inlineCallbacks
    def on_pull_request(self, origin, versions):
        logger.debug("on_pull_request origin=%s", origin)

        response = yield Pdu.after_transaction(
            transaction_id,
            origin,
            self.server_name
        )

        if not response:
            response = []

        defer.returnValue((200, self._wrap_pdus(response)))

    def _wrap_pdus(self, pdu_list):
        return Transaction(
            pdus=[p.get_dict() for p in pdu_list],
            origin=self.server_name,
            ts=int(time.time() * 1000)
        ).get_dict()

    @defer.inlineCallbacks
    def _handle_new_pdu(self, pdu):
        logger.debug(
            "_handle_new_pdu %s from %s", str(pdu.pdu_id), pdu.origin
        )

        # Check if we've seen it before. If we have then we ignore
        # it (unless we have only seen an outlier before)
        existing = yield Pdu.get_persisted_pdu(pdu.pdu_id, pdu.origin)
        if existing and (not existing.outlier or pdu.outlier):
            # We've already seen it, so we ignore it.
            defer.returnValue({})
            return

        # If we are a "new" pdu, we check to see if we have seen the pdus
        # it references. (Unless we are an outlier)
        is_new = yield pdu.is_new()
        if is_new and not pdu.outlier:
            # We only paginate backwards if we seem to be missing something
            # that is before the current min_depth for a context - i.e.,
            # we don't want to paginate backwards.

            min_depth = yield run_interaction(
                PduQueries.get_min_depth,
                pdu.context
            )

            # If min_depth is None, that means that we haven't seen this
            # context before, so we don't go backwards yet.
            if min_depth and pdu.depth > min_depth:
                for pdu_id, origin in pdu.prev_pdus:
                    exists = yield Pdu.get_persisted_pdu(pdu_id, origin)
                    if not exists:
                        logger.debug("Requesting pdu %s %s", pdu_id, origin)
                        # Oh no! We better request it.
                        yield self.get_pdu(
                            pdu.origin,
                            pdu_id=pdu_id,
                            pdu_origin=origin
                        )
                        logger.debug("Processed pdu %s %s", pdu_id, origin)

        # Persist the Pdu, but don't mark it as processed yet.
        yield pdu.persist_received()

        # XXX: Do we want to temporarily persist here, instead of waiting
        # for us to fetch any missing Pdus?

        if pdu.is_state:
            res = yield self._handle_state(pdu, existing)
            defer.returnValue(res)
            return
        else:
            ret = yield self.handler.on_receive_pdu(pdu)

            yield pdu.mark_as_processed()

            defer.returnValue(ret)

    @defer.inlineCallbacks
    def _handle_state(self, pdu, existing):
        logger.debug(
            "_handle_state pdu: %s %s",
            pdu.pdu_id, pdu.origin
        )

        if not existing:
            # Work out if the state has changed. If so hit the state change
            # callback.

            # XXX: RACES?!

            # Fetch any missing state pdus we might be missing
            while True:
                r = yield run_interaction(
                    StateQueries.get_next_missing_pdu,
                    pdu
                )
                if r:
                    logger.debug(
                        "_handle_state getting pdu: %s %s",
                        r.pdu_id, r.origin
                    )
                    yield self.get_pdu(
                        pdu.origin,
                        pdu_id=r.pdu_id,
                        origin=r.origin,
                        outlier=True
                    )
                else:
                    break

            logger.debug("_handle_state updating state")

            was_updated = yield run_interaction(
                StateQueries.handle_new_state,
                pdu
            )

            logger.debug("_handle_state was_updated %s", repr(was_updated))

            if was_updated:
                logger.debug(
                    "Notifying about new state: %s %s",
                    pdu.pdu_id, pdu.origin
                )
                yield self.handler.on_state_change(pdu)

        if not pdu.outlier:
            logger.debug(
                "Notifying about new pdu: %s %s",
                pdu.pdu_id, pdu.origin
            )

            # Inform callback
            ret = yield self.handler.on_receive_pdu(pdu)

            # Mark this Pdu as processed
            yield pdu.mark_as_processed()

            defer.returnValue(ret)
        else:
            defer.returnValue({})


class ReplicationHandler(object):
    def on_receive_pdu(self, pdu):
        raise NotImplementedError("on_receive_pdu")

    def on_state_change(self, pdu):
        raise NotImplementedError("on_state_change")


class _TransactionQueue(object):
    """ This class makes sure we only have one transaction in flight at
        a time for a given destination.

        It batches pending PDUs into single transactions.
    """

    def __init__(self, server_name, transport_layer):

        self.server_name = server_name
        self.transport_layer = transport_layer

        # Is a mapping from destinations -> deferreds. Used to keep track
        # of which destinations have transactions in flight and when they are
        # done
        self.pending_transactions = {}

        # Is a mapping from destination -> list of
        # tuple(pending pdus, deferred, order)
        self.pending_pdus_list = {}

    @defer.inlineCallbacks
    def enqueue_pdu(self, pdu, order):
        # We loop through all destinations to see whether we already have
        # a transaction in progress. If we do, stick it in the pending_pdus
        # table and we'll get back to it later.

        destinations = [
            d for d in pdu.destinations
            if d != self.server_name
        ]

        logger.debug("Sending to: %s" % str(destinations))

        if not destinations:
            return

        deferred_list = []

        for destination in destinations:
            deferred = defer.Deferred()
            self.pending_pdus_list.setdefault(destination, []).append(
                (pdu, deferred, order)
            )

            self._attempt_new_transaction(destination)

            yield deferred_list.append(deferred)

    @defer.inlineCallbacks
    def _attempt_new_transaction(self, destination):
        if destination in self.pending_transactions:
            return

        # tuple_list is a list of (pending_pdu, deferred, order)
        tuple_list = self.pending_pdus_list.pop(destination, None)

        if not tuple_list:
            return

        logger.debug("TX [%s] Attempting new transaction", destination)

        try:
            # Sort based on the order field
            tuple_list.sort(key=lambda t: t[2])

            logger.debug("TX [%s] Persisting transaction...", destination)

            pdus = [p[0] for p in tuple_list]

            transaction = Transaction.create_new(
                origin=self.server_name,
                destination=destination,
                pdus=pdus,
            )

            yield transaction.prepare_to_send()

            logger.debug("TX [%s] Persisted transaction", destination)
            logger.debug("TX [%s] Sending transaction...", destination)

            # Actually send the transaction
            code, response = yield self.transport_layer.send_transaction(
                transaction
            )

            logger.debug("TX [%s] Sent transaction", destination)
            logger.debug("TX [%s] Marking as delivered...", destination)

            yield transaction.delivered(code, response)

            logger.debug("TX [%s] Marked as delivered", destination)
            logger.debug("TX [%s] Yielding to callbacks...", destination)

            for _, deferred, _ in tuple_list:
                if code == 200:
                    deferred.callback(None)
                else:
                    deferred.errback(RuntimeError("Got status %d" % code))

                # Ensures we don't continue until all callbacks on that
                # deferred have fired
                yield deferred

            logger.debug("TX [%s] Yielded to callbacks", destination)

        except Exception as e:
            logger.error("TX Problem in _attempt_transaction")

            # We capture this here as there as nothing actually listens
            # for this finishing functions deferred.
            logger.exception(e)

            for _, deferred, _ in tuple_list:
                deferred.errback(e)
                yield deferred

        finally:
            # We want to be *very* sure we delete this after we stop processing
            self.pending_transactions.pop(destination, None)

            # Check to see if there is anything else to send.
            self._attempt_new_transaction(destination)


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

    """ A list of keys that we persist in the database. The column names are
    the same
    """

    # HACK to get unique tx id
    _next_pdu_id = int(time.time() * 1000)

    # TODO: We need to make this properly load content rather than
    # just leaving it as a dict. (OR DO WE?!)

    def __init__(self, destinations=[], is_state=False, prev_pdus=[],
                 outlier=False, **kwargs):
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

    @staticmethod
    @defer.inlineCallbacks
    def current_state(context):
        """ Get a list of PDUs representing the current state of a context.

        Args:
            context (str): The context we're interested in.

        Returns:
            Deferred: Results in a `list` of Pdus
        """

        results = yield run_interaction(
            PduQueries.get_current_state,
            context
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    @classmethod
    def _from_pdu_tuple(cls, pdu_tuple):
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

    @staticmethod
    @defer.inlineCallbacks
    def get_persisted_pdu(pdu_id, pdu_origin):
        """ Get's a specific PDU from the database.

        Args:
            pdu_id (str): The PDU ID.
            pdu_origin (str): The PDU origin.

        Retruns:
            Deferred: Results in a Pdu
        """
        pdu_tuple = yield run_interaction(
            PduQueries.get_pdu,
            pdu_id, pdu_origin
        )

        defer.returnValue(Pdu._from_pdu_tuple(pdu_tuple))

    def persist_received(self):
        """ Store this PDU we received in the database.

        Args:
            is_out_of_order (bool):

        Returns:
            Deferred
        """

        return self._persist()

    @defer.inlineCallbacks
    def persist_outgoing(self):
        """ Store this PDU we are sending in the database.

        Returns:
            Deferred
        """

        ret = yield self._persist()

        # This is safe to do since if *we* are sending something, then we must
        # have seen everything we reference (hopefully).
        if self.is_state:
            yield run_interaction(
                StateQueries.handle_new_state,
                self
            )

        defer.returnValue(ret)

    def mark_as_processed(self):
        """ Mark this Pdu as having been processed.

        Returns:
            Deferred
        """
        return run_interaction(
            PduQueries.mark_as_processed,
            self.pdu_id, self.origin
        )

    @defer.inlineCallbacks
    def _persist(self):
        kwargs = copy.copy(self.__dict__)
        del kwargs["content"]
        kwargs["content_json"] = json.dumps(self.content)
        kwargs["unrecognized_keys"] = json.dumps(kwargs["unrecognized_keys"])

        logger.debug("Persisting: %s", repr(kwargs))

        if self.is_state:
            ret = yield run_interaction(
                PduQueries.insert_state,
                **kwargs
            )
        else:
            ret = yield run_interaction(
                PduQueries.insert,
                **kwargs
            )

        yield run_interaction(
            PduQueries.update_min_depth,
            self.context, self.depth
        )

        defer.returnValue(ret)

    @defer.inlineCallbacks
    def populate_previous_pdus(self):
        """ Populates the prev_pdus field with the current most recent pdus.
        This is used when we are creating new Pdus for a context.

        Also populates the `versions` field with the correct value.

        Also populates prev_state_* for state_pdus.

        Returns:
            Deferred: Succeeds when prev_pdus have been successfully updated.
        """

        results = yield run_interaction(
            PduQueries.get_prev_pdus,
            self.context
        )

        self.prev_pdus = [(p_id, origin) for p_id, origin, _ in results]

        vs = [int(v) for _, _, v in results]
        if vs:
            self.depth = max(vs) + 1
        else:
            self.depth = 0

        if self.is_state:
            curr = yield run_interaction(
                StateQueries.current_state,
                self.context,
                self.pdu_type, self.state_key)

            if curr:
                self.prev_state_id = curr.pdu_id
                self.prev_state_origin = curr.origin
            else:
                self.prev_state_id = None
                self.prev_state_origin = None

    @staticmethod
    @defer.inlineCallbacks
    def after_transaction(transaction_id, destination, origin):
        """ Get's a list of PDUs that we sent to a given destination after
        a transaction_id.

        Args:
            transaction_id (str): The transaction_id of the last transaction
                they saw.
            destination (str): The remote home server address.
            origin (str): The local home server address.

        Results:
            Deferred: A list of Pdus.
        """
        results = yield run_interaction(
            PduQueries.get_after_transaction,
            transaction_id,
            destination,
            origin
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    @staticmethod
    @defer.inlineCallbacks
    def paginate(context, pdu_list, limit):
        results = yield run_interaction(
            PduQueries.paginate,
            context, pdu_list, limit
        )

        defer.returnValue([Pdu._from_pdu_tuple(p) for p in results])

    def is_new(self):
        return run_interaction(
            PduQueries.is_new,
            pdu_id=self.pdu_id,
            origin=self.origin,
            context=self.context,
            depth=self.depth
        )


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
        "pdus",  # This get's converted to a list of Pdu's
    ]

    internal_keys = [
        "transaction_id",
        "destination",
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

    def have_responded(self):
        """ Have we responded to this transaction?

        Returns:
            Deferred: The result of the deferred is None if we have *not*
            already responded to the transaction (or this is a fake
            transaction without a transaction_id), or a tuple of the form
            `(response_code, response)`, where `response` is a dict which will
            be used as the json response body.
        """
        if not self.transaction_id:
            # This is a fake transaction, which we always process.
            return defer.succeed(None)

        return run_interaction(
            TransactionQueries.get_response_for_received,
            self.transaction_id, self.origin
        )

    def set_response(self, code, response):
        """ Set's how we responded to this transaction. This only makes sense
        for actual transactions with transaction_ids, rather than transactions
        generated from http responses.

        Args:
            code (int): The HTTP status code we returned
            response (dict): The un-json-encoded response body we returned.

        Returns:
            Deferred: Succeeds after we successfully persist the response.
        """
        if not self.transaction_id:
            # This is a fake transaction, which we can't respond to.
            return defer.succeed(None)

        return run_interaction(
            TransactionQueries.set_recieved_txn_response,
            self.transaction_id,
            self.origin,
            code,
            json.dumps(response)
        )

    def persist_as_received(self, response_code, response_json):
        """ Saves this transaction into the received transactions table.

        Args:
            response_code (int): The HTTP response code we responded with.
            response_json (dict): The response body we returned

        Response:
            Deferred: Succeeds after we successfully persist.
        """

        return run_interaction(
            TransactionQueries.insert_received,
            ReceivedTransactionsTable.EntryType(
                transaction_id=self.transaction_id,
                origin=self.origin,
                ts=self.ts,
                response_code=response_code,
                response_json=json.dumps(response_json)
            ),
            self.previous_ids
        )

    @defer.inlineCallbacks
    def prepare_to_send(self):
        """ Prepares this transaction for sending. Persists the transaction and
        computes the correct value for the prev_ids list.

        Returns:
            Deferred: Succeeds when the transaction is ready for transmission.
        """

        self.prev_ids = yield run_interaction(
            TransactionQueries.prep_send_transaction,
            self.transaction_id,
            self.destination,
            self.ts,
            [(p["pdu_id"], p["origin"]) for p in self.pdus]
        )

    def delivered(self, response_code, response_json):
        """ Marks this outgoing transaction as delivered.

        Args:
            response_code (int): The HTTP response code we recieved.
            response_json (dict): The response body.

        Returns:
            Deferred: Succeeds after we persisted the result
        """
        return run_interaction(
            TransactionQueries.delivered_txn,
            self.transaction_id,
            self.destination,
            response_code,
            json.dumps(response_json)
        )