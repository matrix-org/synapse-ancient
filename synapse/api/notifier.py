# -*- coding: utf-8 -*-


class Notifier(object):

    def __init__(self, hs):
        self.store = hs.get_event_data_store()

    def store_events_for(self, user_id=None, from_tok=None):
        """Store all incoming events for this user. This should be paired with
        get_events_for to return chunked data.

        Args:
            user_id (str): The user to monitor incoming events for.
            from_tok (str): The token to monitor incoming events from.
        """
        pass

    def purge_events_for(self, user_id=None):
        """Purges any stored events for this user.

        Args:
            user_id (str): The user to purge stored events for.
        """
        pass

    def get_events_for(self, user_id=None, timeout=None):
        """Retrieve stored events for this user, waiting if necessary.

        Args:
            user_id (str): The user to get events for.
            timeout (int): The time in seconds to wait before giving up.
        Returns:
            A dict containing the chunk data, or None if there were no events
            before the timeout expired.
        """
        pass
