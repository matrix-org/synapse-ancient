# -*- coding: utf-8 -*-


@staticmethod
def _build_where_version(self, from_version=None, to_version=None):
    """ Builds a where clause for the specified versions.

    Args:
        from_version : The version to start from
        to_version : The version to end up at.
    Returns:
        A dict with keys "where", "params", "orderby" whose values can be
        used with DBObject.find : E.g.
        {
          "where" : "id < ? AND id > ?",
          "params" : [from_version, to_version]
          "orderby" : "id ASC"
        }
    """

    # sanity check
    if not from_version and to_version:
        raise IndexError("Cannot have to version without from version.")

    orderby = "id ASC"
    min_ver = from_version
    max_ver = to_version
    where = "1"
    where_arr = []
    if from_version > to_version and to_version is not None:
        # going backwards
        orderby = "id DESC"
        min_ver = to_version
        max_ver = from_version

    if from_version:
        where += " AND id > ?"
        where_arr.append(min_ver)
    if to_version:
        where += " AND id < ?"
        where_arr.append(max_ver)

    return {"where": where, "params": where_arr, "orderby": orderby}