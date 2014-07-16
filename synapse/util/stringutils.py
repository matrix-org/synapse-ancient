# -*- coding: utf-8 -*-
from synapse.api.errors import SynapseError
import random
import string


def origin_from_ucid(ucid):
    return ucid.split("@", 1)[1]


def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for _ in xrange(length))


class JSONTemplate(object):
    STR = "str"
    INT = "int"
    LIST = "list"
    OBJ = "object"

    TYPE_MAP = {
        unicode: STR,
        dict: OBJ
    }

    def __init__(self, required_keys_values):
        """ Make a JSON template for required top-level keys.

        Args:
            required_keys_values : A dict containing the
                                   top-level JSON key and a template type.
        """
        self.template = self._make_template(required_keys_values)

    def check_json(self, content, raises=True):
        """Checks the given JSON content abides by the rules of the template.

        Args:
            content : A JSON object to check.
            raises: True to raise a SynapseError if the check fails.
        Returns:
            True if the content passes the template.
        """
        err_msg = None
        for key in self.template:
            if key not in content:
                err_msg = "Missing %s key" % key
                break
            try:
                if (JSONTemplate.TYPE_MAP[type(content[key])] !=
                                                            self.template[key]):
                    err_msg = "Key %s is of the wrong type." % key
                    break
            except KeyError:
                err_msg = "Key %s is of the wrong type." % key
                break

        if err_msg:
            if raises:
                raise SynapseError(400, err_msg)
            else:
                return False
        else:
            return True

    def _make_template(self, required_keys_values):
        template = {}
        for key in required_keys_values:
            template[key] = required_keys_values[key]
        return template