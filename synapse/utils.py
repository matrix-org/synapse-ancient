# -*- coding: utf-8 -*-


def origin_from_ucid(ucid):
    return ucid.split("@", 1)[1]
