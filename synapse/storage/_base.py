import logging

from synapse.api.errors import StoreError


logger = logging.getLogger(__name__)


class SQLBaseTransaction(object):
    "Wrapper for a db transaction object"

    def __init__(self, hs, transaction):
        self.hs = hs
        self.txn = transaction

    def cursor_to_dict(self, cursor):
        """Converts a SQL cursor into an list of dicts.

        Args:
            cursor : The DBAPI cursor which has executed a query.
        Returns:
            A list of dicts where the key is the column header.
        """
        col_headers = list(column[0] for column in cursor.description)
        results = list(
            dict(zip(col_headers, row)) for row in cursor.fetchall()
        )
        return results

    def exec_single_with_result(self, query, func, *args):
        """Runs a single query for a result set.

        Args:
            txn - Cursor transaction
            query - The query string to execute
            func - The function which can resolve the cursor results to
                something
            meaningful.
            *args - Query args.
        Returns:
            The result of func(results)
        """
        logger.debug("[SQL] %s  Args=%s Func=%s", query, args, func.__name__)
        cursor = self.txn.execute(query, args)
        return func(cursor)

    def exec_single(self, query, *args):
        """Runs a single query, returning nothing."""
        logger.debug("[SQL] %s  Args=%s", query, args)
        self.txn.execute(query, args)

    # "Simple" SQL API methods that operate on a single table with no JOINs,
    # no complex WHERE clauses, just a dict of values for columns.

    def _simple_insert(self, table, values):
        """Executes an INSERT query on the named table.

        Args:
            table : string giving the table name
            values : dict of new column names and values for them
        """
        sql = "INSERT INTO %s (%s) VALUES(%s)" % (
            table,
            ", ".join(k for k in values),
            ", ".join("?" for k in values)
        )

        self.txn.execute(sql, values.values())

    def _simple_select_one(self, table, keyvalues, retcols, allow_none=False):
        """Executes a SELECT query on the named table, which is expected to
        return a single row, returning a single column from it.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            retcols : list of strings giving the names of the columns to return

            allow_none : If true, return None instead of failing if the SELECT
              statement returns no rows
        """
        return self._simple_selectupdate_one(
            table, keyvalues, retcols=retcols, allow_none=allow_none
        )

    def _simple_select_one_onecol(self, table, keyvalues, retcol,
                                  allow_none=False):
        """Executes a SELECT query on the named table, which is expected to
        return a single row, returning a single column from it."

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            retcol : string giving the name of the column to return
        """
        ret = self._simple_select_one(
            table=table,
            keyvalues=keyvalues,
            retcols=[retcol],
            allow_none=allow_none
        )

        if ret:
            return ret[retcol]
        else:
            return None

    def _simple_select_list(self, table, keyvalues, retcols):
        """Executes a SELECT query on the named table, which may return zero or
        more rows, returning the result as a list of dicts.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the rows with
            retcols : list of strings giving the names of the columns to return
        """
        sql = "SELECT %s FROM %s WHERE %s" % (
            ", ".join(retcols),
            table,
            " AND ".join("%s = ?" % (k) for k in keyvalues)
        )
        txn = self.txn
        txn.execute(sql, keyvalues.values())
        return self.cursor_to_dict(txn)

    def _simple_update_one(self, table, keyvalues, updatevalues, retcols=None):
        """Executes an UPDATE query on the named table, setting new values for
        columns in a row matching the key values.

        Args:
            txn : transaction for accessing database
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
            updatevalues : dict giving column names and values to update
            retcols : optional list of column names to return

        If present, retcols gives a list of column names on which to perform
        a SELECT statement *before* performing the UPDATE statement. The values
        of these will be returned in a dict.

        These are performed within the same transaction, allowing an atomic
        get-and-set.  This can be used to implement compare-and-set by putting
        the update column in the 'keyvalues' dict as well.
        """
        return self._simple_selectupdate_one(
            table, keyvalues, updatevalues, retcols=retcols
        )

    def _simple_selectupdate_one(self, table, keyvalues,
                                 updatevalues=None, retcols=None,
                                 allow_none=False):
        """ Combined SELECT then UPDATE."""
        if retcols:
            select_sql = "SELECT %s FROM %s WHERE %s" % (
                ", ".join(retcols),
                table,
                " AND ".join("%s = ?" % (k) for k in keyvalues)
            )

        if updatevalues:
            update_sql = "UPDATE %s SET %s WHERE %s" % (
                table,
                ", ".join("%s = ?" % (k) for k in updatevalues),
                " AND ".join("%s = ?" % (k) for k in keyvalues)
            )

        txn = self.txn
        ret = None
        if retcols:
            txn.execute(select_sql, keyvalues.values())

            row = txn.fetchone()
            if not row:
                if allow_none:
                    return None
                raise StoreError(404, "No row found")
            if txn.rowcount > 1:
                raise StoreError(500, "More than one row matched")

            ret = dict(zip(retcols, row))

        if updatevalues:
            txn.execute(
                update_sql, updatevalues.values() + keyvalues.values()
            )

            if txn.rowcount == 0:
                raise StoreError(404, "No row found")
            if txn.rowcount > 1:
                raise StoreError(500, "More than one row matched")

        return ret

    def _simple_delete_one(self, table, keyvalues):
        """Executes a DELETE query in the named table, expecting to delete a
        single row.

        Args:
            table : string giving the table name
            keyvalues : dict of column names and values to select the row with
        """
        sql = "DELETE FROM %s WHERE %s" % (
            table,
            " AND ".join("%s = ?" % (k) for k in keyvalues)
        )

        txn = self.txn
        txn.execute(sql, keyvalues.values())
        if txn.rowcount == 0:
            raise StoreError(404, "No row found")
        if txn.rowcount > 1:
            raise StoreError(500, "more than one row matched")

    def _simple_max_id(self, table):
        """Executes a SELECT query on the named table, expecting to return the
        max value for the column "id".

        Args:
            table : string giving the table name
        """
        sql = "SELECT MAX(id) AS id FROM %s" % table

        txn = self.txn
        txn.execute(sql)
        max_id = self.cursor_to_dict(txn)[0]["id"]
        if max_id is None:
            return 0
        return max_id
