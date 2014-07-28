import logging

from synapse.api.errors import StoreError


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

    # "Simple" SQL API methods that operate on a single table with no JOINs,
    # no complex WHERE clauses, just a dict of values for columns.

    def interact_simple_insert(self, table, values):
        """Executes an INSERT query on the named table.

        Args:
            table : string giving the table name
            values : dict of new column names and values for them
        """
        sql = "INSERT INTO %s (%s) VALUES(%s)" % (
                table,
                ", ".join([k for k in values]),
                ", ".join(["?" for k in values]))

        def func(txn):
            txn.execute(sql, values.values())
        self._db_pool.runInteraction(func)

    def interact_simple_select_one_one(self, table, keyvalues, retcol):
        """Executes a SELECT query on the named table, which is expected to
        return a single row, returning a single column from it.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            retcol : string giving the name of the column to return
        """
        sql = "SELECT %s FROM %s WHERE %s" % (
                retcol,
                table,
                " AND ".join(["%s = ?" % (k) for k in keyvalues]))

        def func(txn):
            txn.execute(sql, keyvalues.values())

            row = txn.fetchone()
            if not row:
                raise StoreError(404, "No row found")
            if txn.rowcount > 1:
                raise StoreError(500, "More than one row matched")

            return row[0]
        return self._db_pool.runInteraction(func)

    def interact_simple_update_one(self, table, keyvalues, updatevalues):
        """Exectes an UPDATE query on the named table, setting new values for
        columns in a row matching the key values.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            updatevalues : dict giving column names and values to update
        """
        sql = "UPDATE %s SET %s WHERE %s" % (
                table,
                ", ".join(["%s = ?" % (k) for k in updatevalues]),
                " AND ".join(["%s = ?" % (k) for k in keyvalues]))

        def func(txn):
            txn.execute(sql, updatevalues.values() + keyvalues.values())
            if txn.rowcount == 0:
                raise StoreError(404, "No row found")
            if txn.rowcount > 1:
                raise StoreError(500, "More than one row matched")
        return self._db_pool.runInteraction(func)
