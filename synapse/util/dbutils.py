# -*- coding: utf-8 -*-


class DbPool(object):
    pool = None

    @staticmethod
    def set(pool):
        DbPool.pool = pool

    @staticmethod
    def get():
        return DbPool.pool
