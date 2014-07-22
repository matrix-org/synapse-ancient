# -*- coding: utf-8 -*-


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