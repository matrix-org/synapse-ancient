# -*- coding: utf-8 -*-

from twisted.internet import defer

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


@defer.inlineCallbacks
def get_next_version(context):
    results = yield PduContextForwardExtremeties.findBy(context=context)

    defer.returnValue([(r["pdu_id"], r["origin"]) for r in results])

    for r in results:
        r.delete()