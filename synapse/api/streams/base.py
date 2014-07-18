# -*- coding: utf-8 -*-
"""This module contains base classes and helper functions for streams."""


class FilterStream(object):

    """ An interface for streaming data as chunks. """

    TOK_START = "START"
    TOK_END = "END"
    DIRECTIONS = ["f", "b"]

    def get_chunk(self, from_tok=None, to_tok=None, direction=None, limit=None):
        """ Return the next chunk in the stream.

        Args:
            from_tok (str): The from token
            to_tok (str): The to token
            direction (str): The direction to navigate in.
            limit (int) : The maximum number of results to return.
        Returns:
            A dict containing the new start token "start", the new end token
            "end" and the data "chunk" as a list.
        """
        raise NotImplementedError()


class StreamData(object):

    """ An interface for obtaining streaming data from a table. """

    def __init__(self, store):
        self.store = store

    def get_rows(self, user_id, from_pkey, to_pkey):
        """ Get event stream data between the specified pkeys.

        Args:
            user_id : The user's ID
            from_pkey : The starting pkey.
            to_pkey : The end pkey. May be -1 to mean "latest".
        Returns:
            A tuple containing the list of event stream data and the last pkey.
        """
        raise NotImplementedError()


@staticmethod
def _build_where_version(self, from_version=None, to_version=None):
    """ Builds a where clause for the specified versions.

    Args:
        from_version : The version to start from
        to_version : The version to end up at.
    Returns:
        A dict with keys "where", "params", "orderby" whose values can be
        used with DBObject.find : E.g.
        {
          "where" : "id < ? AND id > ?",
          "params" : [from_version, to_version]
          "orderby" : "id ASC"
        }
    """

    # sanity check
    if not from_version and to_version:
        raise IndexError("Cannot have to version without from version.")

    orderby = "id ASC"
    min_ver = from_version
    max_ver = to_version
    where = "1"
    where_arr = []
    if from_version > to_version and to_version is not None:
        # going backwards
        orderby = "id DESC"
        min_ver = to_version
        max_ver = from_version

    if from_version:
        where += " AND id > ?"
        where_arr.append(min_ver)
    if to_version:
        where += " AND id < ?"
        where_arr.append(max_ver)

    return {"where": where, "params": where_arr, "orderby": orderby}
