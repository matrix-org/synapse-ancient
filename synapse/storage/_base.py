import logging


logger = logging.getLogger(__name__)


class SQLBaseStore(object):

    def __init__(self, hs):
        self._db_pool = hs.get_db_pool()

    def exec_single_with_result(self, txn, query, func, *args):
        """Runs a single query for a result set.

        Args:
            txn - Cursor transaction
            query - The query string to execute
            func - The function which can resolve the cursor results to something
            meaningful.
            *args - Query args.
        Returns:
            The result of func(results)
        """
        logger.debug("[SQL] %s  Args=%s Func=%s" % (
            query, args, func.__name__))

        cursor = txn.execute(query, args)
        return func(cursor)

    def exec_single(self, txn, query, *args):
        """Runs a single query, returning nothing."""
        logger.debug("[SQL] %s  Args=%s" % (query, args))
        txn.execute(query, args)
