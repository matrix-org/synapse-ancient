# -*- coding: utf-8 -*-
from synapse.api.errors import SynapseError
from synapse.federation.units import JsonEncodedObject


class SynapseEvent(JsonEncodedObject):

    """Base class for Synapse events. These are JSON objects which must abide by
    a certain well-defined structure.
    """

    # Attributes that are currently assumed by the federation side:
    # Mandatory:
    # - event_id
    # - room_id
    # - type
    # - is_state
    #
    # Optional:
    # - state_key (mandatory when is_state is True)
    # - prev_events (these can be filled out by the federation layer itself.)
    # - prev_state

    valid_keys = [
        "event_id",
        "type",
        "room_id",
        "user_id",  # sender/initiator
        "content",  # HTTP body, JSON
    ]

    internal_keys = [
        "is_state",
        "state_key",
        "prev_events",
        "prev_state",
        "depth",
    ]

    required_keys = [
        "event_id",
        "room_id",
        "content",
    ]

    def __init__(self, raises=True, **kwargs):
        super(SynapseEvent, self).__init__(**kwargs)
        if "content" in kwargs:
            self.check_json(self.content, raises=raises)

    def get_content_template(self):
        """ Retrieve the JSON template for this event as a dict.

        The template must be a dict representing the JSON to match. Only
        required keys should be present. The values of the keys in the template
        are checked via type() to the values of the same keys in the actual
        event JSON.

        NB: If loading content via json.loads, you MUST define strings as
        unicode.

        For example:
            Content:
                {
                    "name": u"bob",
                    "age": 18,
                    "friends": [u"mike", u"jill"]
                }
            Template:
                {
                    "name": u"string",
                    "age": 0,
                    "friends": [u"string"]
                }
            The values "string" and 0 could be anything, so long as the types
            are the same as the content.
        """
        raise NotImplementedError("get_content_template not implemented.")

    def check_json(self, content, raises=True):
        """Checks the given JSON content abides by the rules of the template.

        Args:
            content : A JSON object to check.
            raises: True to raise a SynapseError if the check fails.
        Returns:
            True if the content passes the template. Returns False if the check
            fails and raises=False.
        Raises:
            SynapseError if the check fails and raises=True.
        """
        # recursively call to inspect each layer
        err_msg = self._check_json(content, self.get_content_template(), raises)
        if err_msg:
            if raises:
                raise SynapseError(400, err_msg)
            else:
                return False
        else:
            return True

    def _check_json(self, content, template, raises):
        for key in template:
            if key not in content:
                return "Missing %s key" % key

            if type(content[key]) != type(template[key]):
                return "Key %s is of the wrong type." % key

            if type(content[key]) == dict:
                # we must go deeper
                msg = self._check_json(content[key], template[key], raises)
                if msg:
                    return msg