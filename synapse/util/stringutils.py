# -*- coding: utf-8 -*-
from synapse.api.errors import SynapseError
import random
import string


def origin_from_ucid(ucid):
    return ucid.split("@", 1)[1]


def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for _ in xrange(length))


class JSONTemplate(object):

    def __init__(self, template):
        """ Make a JSON template for required top-level keys.

        Args:
            template : A dict representing the JSON to match. Only required
                       keys should be present, and the values are mapped
                       directly to the types of the content via type() so the
                       value content doesn't matter, just the type does.
        """
        self.json_template = template

    def check_json(self, content, raises=True):
        """Checks the given JSON content abides by the rules of the template.

        Args:
            content : A JSON object to check.
            raises: True to raise a SynapseError if the check fails.
        Returns:
            True if the content passes the template.
        """
        # recursively call to inspect each layer
        err_msg = self._check_json(content, self.json_template, raises)
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