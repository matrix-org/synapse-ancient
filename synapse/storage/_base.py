import logging

from twisted.internet import defer

from synapse.api.errors import StoreError


logger = logging.getLogger(__name__)


class SQLBaseStore(object):

    def __init__(self, hs):
        self._db_pool = hs.get_db_pool()

    def cursor_to_dict(self, cursor):
        """Converts a SQL cursor into an list of dicts.

        Args:
            cursor : The DBAPI cursor which has executed a query.
        Returns:
            A list of dicts where the key is the column header.
        """
        col_headers = list(map(lambda x: x[0], cursor.description))
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(col_headers, row)))
        return results

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

    def interact_simple_select_one(self, table, keyvalues, retcols,
            allow_none=False):
        """Executes a SELECT query on the named table, which is expected to
        return a single row, returning a single column from it.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            retcols : list of strings giving the names of the columns to return

            allow_none : If true, return None instead of failing if the SELECT
              statement returns no rows
        """
        sql = "SELECT %s FROM %s WHERE %s" % (
                ", ".join(retcols),
                table,
                " AND ".join(["%s = ?" % (k) for k in keyvalues]))

        def func(txn):
            txn.execute(sql, keyvalues.values())

            row = txn.fetchone()
            if not row:
                if allow_none:
                    return None
                raise StoreError(404, "No row found")
            if txn.rowcount > 1:
                raise StoreError(500, "More than one row matched")

            return dict(zip(retcols,row))
        return self._db_pool.runInteraction(func)

    @defer.inlineCallbacks
    def interact_simple_select_one_onecol(self, table, keyvalues, retcol,
            allow_none=False):
        """Executes a SELECT query on the named table, which is expected to
        return a single row, returning a single column from it."

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            retcol : string giving the name of the column to return
        """
        ret = yield self.interact_simple_select_one(
                table=table, keyvalues=keyvalues, retcols=[retcol],
                allow_none=allow_none
        )

        if ret:
            defer.returnValue(ret[retcol])
        else:
            defer.returnValue(None)

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
