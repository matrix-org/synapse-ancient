# -*- coding: utf-8 -*-


class EventFactory(object):

    """ A factory for creating synapse events.

    Synapse events are logical entities which process a single event, such as
    sending a message, setting a room topic, etc. These may be wrapped by REST
    events to provide a way for clients to initiate events.

    See synapse.rest.base for information on synapse REST events.
    """

    def __init__(self, event_store):
        self.store = event_store

