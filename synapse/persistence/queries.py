# -*- coding: utf-8 -*-

from twistar.registry import Registry


def get_pdus_after_transaction_id_query():
    return (
        "SELECT pdus.* from transaction_id_to_pdu as t LEFT JOIN pdus "
            "ON t.pdu_id = pdus.pdu_id "
        "WHERE pdus.origin = ? "
            "AND t.transaction_id > ? "
            "AND t.destination = ?"
    )


def get_state_pdus_for_context_query():
    return (
        "SELECT pdus.* from state_pdu "
                "LEFT JOIN pdus ON state_pdu.pdu_row_id = pdus.id "
                "WHERE context = ?"
    )


def get_delete_versions_context_query(N):
    where_clause = ["(pdu_id = ? AND origin = ?)"] * N
    where_clause = " OR ".join(where_clause)
    return (
        "DELETE FROM pdu_context_forward_extremeties "
        "WHERE context = ? AND (%s)" % where_clause
    )


def delete_forward_context_extremeties(context, pdu_list):
    """ Given a list of ids [(pdu_id, origin),...], delete them from the
        pdu_context_forward_extremeties table
    """
    query = get_delete_versions_context_query(len(pdu_list))

    # The where clause args need to be [context, id1, origin1, id2,...]
    where_args = [context] + [item for sublist in pdu_list for item in sublist]

    return Registry.DBPOOL.runQuery(query, where_args)