# -*- coding: utf-8 -*-

from twistar.dbobject import DBObject


class PduDbEntry(DBObject):
    TABLENAME = "pdus"  # Table name

    def dict(self):
        return self.__dict__


class PduDestinationEntry(DBObject):
    TABLENAME = "pdu_destinations"  # Table name


class PduContextEdgesEntry(DBObject):
    TABLENAME = "pdu_context_edges"  # Table name


class PduContextForwardExtremeties(DBObject):
    TABLENAME = "pdu_context_forward_extremeties"  # Table name
