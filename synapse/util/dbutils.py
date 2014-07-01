# -*- coding: utf-8 -*-


DBPOOL = None


def set_db_pool(pool):
    global DBPOOL
    DBPOOL = pool


def get_db_pool():
    return DBPOOL

