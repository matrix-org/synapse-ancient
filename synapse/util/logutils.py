# -*- coding: utf-8 -*-

from inspect import getcallargs

import logging


def log_function(f):
    """ Function decorator that logs every call to that function.
    """
    func_name = f.__name__
    lineno = f.func_code.co_firstlineno
    pathname = f.func_code.co_filename

    def wrapped(*args, **kwargs):
        bound_args = getcallargs(f, *args, **kwargs)

        def format(value):
            r = str(value)
            if len(r) > 50:
                r = r[:50] + "..."
            return r

        func_args = ["%s=%s" % (k, format(v)) for k, v in bound_args.items()]

        msg_args = {
            "func_name": func_name,
            "args": ", ".join(func_args)
        }

        record = logging.LogRecord(
            name=f.__module__,
            level=logging.DEBUG,
            pathname=pathname,
            lineno=lineno,
            msg="Invoked '%(func_name)s' with args: %(args)s",
            args=msg_args,
            exc_info=None
        )

        logging.getLogger(record.name).handle(record)

        return f(*args, **kwargs)

    return wrapped
