# -*- coding: utf-8 -*-

from synapse.api.dbobjects import Message


@staticmethod
def get_messages(self, room_id=None, from_version=None, to_version=None,
                 **kwargs):
    where_dict = self._build_where_version(from_version, to_version)
    if room_id:
        where_dict["where"] += " AND room_id = ?"
        where_dict["params"].append(room_id)

    where_arr = [where_dict["where"]] + where_dict["params"]
    return Message.find(
        where=where_arr,
        orderby=where_dict["orderby"],
        **kwargs
    )