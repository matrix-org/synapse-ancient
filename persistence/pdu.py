# -*- coding: utf-8 -*-

from twisted.internet import defer
from twistar.dbobject import DBObject

from queries import delete_forward_context_extremeties


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
    yield delete_forward_context_extremeties(pdu.context, pdu.previous_pdus)


@defer.inlineCallbacks
def register_pdu_as_sent(pdu):
    """ Called when we have succesfully sent the PDU, so it's safe to update
        the tables.

        Update extremeties table
    """
    yield delete_forward_context_extremeties(pdu.context, pdu.previous_pdus)


@defer.inlineCallbacks
def _add_pdu_to_tables(pdu):
    """ Adds the pdu to the edges and extremeties table.
        DOES NOT DELETE existing extremeties. This should be done only when
        we know the remote sides have seen our message (for outgoing ones)
    """
     # Add new pdu to extremeties table
    extrem = PduContextForwardExtremeties(pdu_id=pdu.pdu_id, origin=pdu.origin)

    dl_list = [extrem.save()]

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