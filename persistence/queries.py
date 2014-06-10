# -*- coding: utf-8 -*-

from twisted.internet import defer
from twistar.registry import Registry
from twistar.utils import createInstances

from pdu import PduDbEntry

from protocol.units import Pdu


def _get_pdus_after_transaction_id_query():
    return (
        "SELECT pdus.* from transaction_id_to_pdu as t LEFT JOIN pdus "
            "ON t.pdu_id = pdus.pdu_id "
        "WHERE pdus.origin = ? "
            "AND t.transaction_id > ? "
            "AND t.destination = ?"
    )


def _get_state_pdus_for_context_query():
    return (
        "SELECT pdus.* from state_pdu "
                "LEFT JOIN pdus ON state_pdu.pdu_row_id = pdus.id "
                "WHERE context = ?"
    )


def _get_delete_versions_context_query(N):
    where_clause = ["(pdu_id = ? AND pdu_origin = ?)"] * N
    where_clause = " OR ".join(where_clause)
    return (
        "DELETE FROM pdu_context_forward_extremeties "
        "WHERE context = ? AND (%s)" % where_clause
    )


@defer.inlineCallbacks
def get_pdus_after_transaction_id(origin, transaction_id, destination):
    """ Given a transaction_id, return all PDUs sent *after* that
        transaction_id to a given destination
    """
    query = _get_pdus_after_transaction_id_query()

    return _load_pdus_from_query(query, origin, transaction_id, destination)


def get_state_pdus_for_context(context):
    """ Given a context, return all state pdus
    """
    query = _get_state_pdus_for_context_query()

    return _load_pdus_from_query(query, context)


@defer.inlineCallbacks
def _load_pdus_from_query(query, *args):
    """ Given the query that loads fetches rows of pdus from the db,
        actually load them as protocol.units.Pdu's
    """
    results = yield Registry.DBPOOL.runQuery(
            query,
            args
        )

    pdus = []

    for r in results:
        i = yield createInstances(PduDbEntry, r)
        pdus.append(Pdu.from_db_entry(i))

    yield defer.DeferredList([p.get_destinations_from_db() for p in pdus])
    yield defer.DeferredList([p.get_previous_pdus_from_db() for p in pdus])

    defer.returnValue(pdus)


def delete_forward_context_extremeties(context, pdu_list):
    """ Given a list of ids [(pdu_id, origin),...], delete them from the
        pdu_context_forward_extremeties table
    """
    query = _get_delete_versions_context_query(len(pdu_list))

    # The where clause args need to be [context, id1, origin1, id2,...]
    where_args = [context] + [item for sublist in pdu_list for item in sublist]

    return Registry.DBPOOL.runQuery(query, where_args)