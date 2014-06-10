# -*- coding: utf-8 -*-

from twisted.internet import defer
from twistar.dbobject import DBObject
from twistar.registry import Registry
from twistar.utils import createInstances

import queries


class PduDbEntry(DBObject):
    TABLENAME = "pdus"  # Table name

    def dict(self):
        return self.__dict__


class PduDestinationEntry(DBObject):
    TABLENAME = "pdu_destinations"  # Table name


class PduContextEdgesEntry(DBObject):
    TABLENAME = "pdu_context_edges"  # Table name


class PduContextForwardExtremeties(DBObject):
    TABLENAME = "pdu_context_forward_extremeties"  # Table name


@defer.inlineCallbacks
def register_new_outgoing_pdu(pdu):
    """ For outgoing pdus, we need to fill out the "previous_pdus" property.
        We do this by querying the current extremeties table.

        Does NOT remove existing extremeties, as we need to wait until
        we know the other side has actually received the pdu.
    """
    results = yield PduContextForwardExtremeties.findBy(context=pdu.context)

    pdu.previous_pdus = [(r["pdu_id"], r["origin"]) for r in results]

    yield _add_pdu_to_tables(pdu)


@defer.inlineCallbacks
def register_remote_pdu(pdu):
    """ Called when we receive a remote pdu.

        Updates the edges + extremeties tables
    """
    yield _add_pdu_to_tables(pdu)
    yield queries.delete_forward_context_extremeties(
        pdu.context, pdu.previous_pdus)


@defer.inlineCallbacks
def register_pdu_as_sent(pdu):
    """ Called when we have succesfully sent the PDU, so it's safe to update
        the tables.

        Update extremeties table
    """
    yield queries.delete_forward_context_extremeties(
        pdu.context, pdu.previous_pdus)


@defer.inlineCallbacks
def _add_pdu_to_tables(pdu):
    """ Adds the pdu to the edges and extremeties table.
        DOES NOT DELETE existing extremeties. This should be done only when
        we know the remote sides have seen our message (for outgoing ones)
    """

    dl_list = []

    # Check to see if we have already received something that refrences this
    # pdu. If yes, we don't consider it an extremity
    result = yield PduContextEdgesEntry.findBy(
            prev_pdu_id=pdu.pdu_id,
            prev_origin=pdu.origin,
            context=pdu.context
        )

    if not result:
        # Add new pdu to extremeties table
        extrem = PduContextForwardExtremeties(
                pdu_id=pdu.pdu_id,
                origin=pdu.origin,
                context=pdu.context
            )

        dl_list.append(extrem.save())

    # Update edges table with new pdu
    for r in pdu.previous_pdus:
        edge = PduContextForwardExtremeties(
                    pdu_id=pdu.pdu_id,
                    origin=pdu.origin,
                    prev_pdu_id=r[0],
                    prev_origin=r[1]
                )
        dl_list.append(edge.save())

    yield defer.DeferredList(dl_list)


@defer.inlineCallbacks
def get_pdus_after_transaction_id(origin, transaction_id, destination):
    """ Given a transaction_id, return all PDUs sent *after* that
        transaction_id to a given destination
    """
    query = queries.get_pdus_after_transaction_id_query()

    return _load_pdu_entries_from_query(query, origin, transaction_id,
                destination)


def get_state_pdus_for_context(context):
    """ Given a context, return all state pdus
    """
    query = queries.get_state_pdus_for_context_query()

    return _load_pdu_entries_from_query(query, context)


@defer.inlineCallbacks
def _load_pdu_entries_from_query(query, *args):
    """ Given the query that loads fetches rows of pdus from the db,
        actually load them as protocol.units.Pdu's
    """
    results = yield Registry.DBPOOL.runQuery(
            query,
            args
        )

    pdus = []

    for r in results:
        db_entry = yield createInstances(PduDbEntry, r)
        pdus.append(db_entry)

    #yield defer.DeferredList([p.get_destinations_from_db() for p in pdus])
    #yield defer.DeferredList([p.get_previous_pdus_from_db() for p in pdus])

    defer.returnValue(pdus)