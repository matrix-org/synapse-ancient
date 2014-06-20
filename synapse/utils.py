# -*- coding: utf-8 -*-


DBPOOL = None


def set_db_pool(pool):
    global DBPOOL
    DBPOOL = pool


def get_db_pool():
    return DBPOOL


def origin_from_ucid(ucid):
    return ucid.split("@", 1)[1]