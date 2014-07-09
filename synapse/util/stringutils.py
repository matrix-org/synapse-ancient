# -*- coding: utf-8 -*-
import string, random


def origin_from_ucid(ucid):
    return ucid.split("@", 1)[1]


def random_string(length):
    return ''.join(random.choice(string.ascii_letters) for _ in xrange(length))