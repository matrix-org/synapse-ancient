# -*- coding: utf-8 -*-
""" Defines a bunch of queries that we may want to run against the database.
"""


def pdus_after_transaction_id():
    """ Returns a query to get all Pdu's from the database that happened after
    a specified transaction and originated from a given home server.

    The query expects 3 arguments:
    (origin, transaction_id, transaction_destination)

    Returns:
        str
    """
    return (
        "SELECT pdus.* from transaction_id_to_pdu as t LEFT JOIN pdus "
            "ON t.pdu_id = pdus.pdu_id "
        "WHERE pdus.origin = ? "
            "AND t.transaction_id > ? "
            "AND t.destination = ?"
    )


def state_pdus_for_context():
    """ Returns a query that selects all current state PDUs for a given context

    The query expects a single argument, which is the name of the context.

    Returns:
        str
    """
    return (
        "SELECT pdus.* from state_pdu "
                "LEFT JOIN pdus ON state_pdu.pdu_row_id = pdus.id "
                "WHERE pdus.context = ?"
    )


def delete_versions_context(N):
    """ Returns a query that will delete all PDU entries from the
    pdu_context_forward_extremeties table.

    The query expects 1 + 2 * N arguments, the first being the context and then
    pairs of pdu_id and pdu_origin.

    Args:
        N (int): The number of entries to delete

    Returns:
        str
    """

    where_clause = ["(pdu_id = ? AND origin = ?)"] * N
    where_clause = " OR ".join(where_clause)
    return (
        "DELETE FROM pdu_context_forward_extremeties "
        "WHERE context = ? AND (%s)" % where_clause
    )


def delete_forward_context_extremeties(context, pdu_list):
    """ Given a list of ids [(pdu_id, origin),...], get's the query and
    arguments to delete from pdu_context_forward_extremeties table
    """

    if not pdu_list:
        raise RuntimeError("pdu_list must be a non-empty list")

    query = delete_versions_context(len(pdu_list))

    # The where clause args need to be [context, id1, origin1, id2,...]
    where_args = [context] + [item for sublist in pdu_list for item in sublist]

    return (query, where_args)


