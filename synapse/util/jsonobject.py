
import copy

class JsonEncodedObject(object):
    """ A common base class for defining protocol units that are represented
    as JSON.

    Attributes:
        unrecognized_keys (dict): A dict containing all the key/value pairs we
            don't recognize.
    """

    valid_keys = []  # keys we will store
    """A list of strings that represent keys we know about
    and can handle. If we have values for these keys they will be
    included in the `dictionary` instance variable.
    """

    internal_keys = []  # keys to ignore while building dict
    """A list of strings that should *not* be encoded into JSON.
    """

    required_keys = []
    """A list of strings that we require to exist. If they are not given upon
    construction it raises an exception.
    """

    def __init__(self, **kwargs):
        """ Takes the dict of `kwargs` and loads all keys that are *valid*
        (i.e., are included in the `valid_keys` list) into the dictionary`
        instance variable.

        Any keys that aren't recognized are added to the `unrecognized_keys`
        attribute.

        Args:
            **kwargs: Attributes associated with this protocol unit.
        """
        for required_key in self.required_keys:
            if required_key not in kwargs:
                raise RuntimeError("Key %s is required" % required_key)

        self.unrecognized_keys = {}  # Keys we were given not listed as valid
        for k, v in kwargs.items():
            if k in self.valid_keys or k in self.internal_keys:
                self.__dict__[k] = v
            else:
                self.unrecognized_keys[k] = v

    def get_dict(self):
        """ Converts this protocol unit into a :py:class:`dict`, ready to be
        encoded as JSON.

        The keys it encodes are: `valid_keys` - `internal_keys`

        Returns
            dict
        """
        d = {
            k: _encode(v) for (k, v) in self.__dict__.items()
            if k in self.valid_keys and k not in self.internal_keys
        }
        d.update(self.unrecognized_keys)
        return copy.deepcopy(d)

    def get_full_dict(self):
        d = {
            k: v for (k, v) in self.__dict__.items()
            if k in self.valid_keys or k in self.internal_keys
        }
        d.update(self.unrecognized_keys)
        return copy.deepcopy(d)

    def __str__(self):
        return "(%s, %s)" % (self.__class__.__name__, repr(self.__dict__))

def _encode(obj):
    if type(obj) is list:
        return [_encode(o) for o in obj]

    if isinstance(obj, JsonEncodedObject):
        return obj.get_dict()

    return obj
