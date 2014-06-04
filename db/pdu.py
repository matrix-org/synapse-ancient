# -*- coding: utf-8 -*-

from twisted.internet import defer
from twistar.dbobject import DBObject
from twistar.registry import Registry
from twistar.utils import createInstances

import json
import time
import copy


class PDU(DBObject):
    """ Persists PDUs into a db.

        This automagically recognizes metadata PDUs and keeps the metadata
        PDUs table up to date.

        Properties:
            - pdu_id
            - context
            - pdu_type
            - origin
            - ts
            - content (automatically converts into content_json)
            - is_state
            - state_key
    """

    TABLENAME = "pdus"  # Table name
    _next_pdu_id = int(time.time())  # XXX Temp. hack to make it unique

    def create(context, pdu_type, origin, ts, content,
            is_state=True, state_key=None):
        p_id = PDU._next_pdu_id
        PDU._next_pdu_id += 1
        return PDU(
                pdu_id=p_id,
                context=context,
                pdu_type=pdu_type,
                origin=origin,
                ts=ts,
                content=content,
                is_state=is_state,
                state_key=state_key
            )

    def create_from_dict(pdu_json):

        unrecognized_keys = copy.deepcopy(pdu_json)

        kwargs = {
                "pdu_id": pdu_json["pdu_id"],
                "version": pdu_json["version"],
                "context": pdu_json["context"],
                "pdu_type": pdu_json["pdu_type"],
                "origin": pdu_json["origin"],
                "ts": pdu_json["ts"],
                "content": pdu_json["content"],
                "is_state": pdu_json.get("is_state", False),
                "state_key": pdu_json.get("state_key")
            }

        for k in kwargs:
            del unrecognized_keys[k]

        return PDU(unrecognized_keys=unrecognized_keys, **kwargs)

    def to_dict(self):
        d = {
                "pdu_id": self.pdu_id,
                "version": self.version,
                "context": self.context,
                "pdu_type": self.pdu_type,
                "origin": self.origin,
                "ts": self.ts,
                "content": self.content,
                "is_state": bool(self.is_state),
                "state_key": self.state_key
            }

        d.update(self.unrecognized_keys)

        return d

    @defer.inlineCallbacks
    def get_current_metadata_pdus(context):
        """ Get all current metatdata PDUs for a given context.
            See MetadataPDU below.
        """
        result = yield Registry.DBPOOL.runQuery(
                "SELECT pdus.* from state_pdu "
                "LEFT JOIN pdus ON state_pdu.pdu_row_id = pdus.id "
                "WHERE context = ?",
                (context,)
            )
        instances = yield createInstances(PDU, result)
        defer.returnValue(instances)
        return

    # INTERNAL
    @defer.inlineCallbacks
    def beforeSave(self):
        # Automagically store self.content as json in content_json column
        if self.content:
            self.content_json = json.dumps(self.content)

        if (self.is_metadata):
            # Just create a new one and insert it. This will replace anything
            # already in there correctly anyway.
            m_pdu = CurrentStatePDUEntry.create_from_pdu(self)
            yield m_pdu.save()

        defer.returnValue(True)

    # INTERNAL
    def afterInit(self):
        # Automagically store self.content as json in content_json column
        if self.content_json:
            self.content = json.loads(self.content_json)

        return True

    # INTERNAL
    @defer.inlineCallbacks
    def refresh(self):
        ret = yield super(DBObject, self).refresh()

        # Automagically store self.content as json in content_json column
        if self.content_json:
            self.content = json.loads(self.content_json)

        defer.returnValue(ret)


class PDUDestination(DBObject):
    """ Stores where each outgoing pdu should be sent to an it'd
        delivery time if delivered
    """
    TABLENAME = "pdu_destinations"

    def create_from_pdu(pdu, destination):
        return PDUDestination(
                pdu_row_id=pdu.id,
                destination=destination,
                delivered_ts=0
            )

    def has_been_delivered(self):
        return self.delivered_ts > 0


class CurrentStatePDUEntry(DBObject):
    """ For a given context, we need to be able to efficiently get PDUs that
        are considered to be a) state and b) "current"
        State pdu's are considered current if we have not since seen any
        pdu's with the same (context, pdu_type, metadata_key) tuple.
        We do this by keeping the track of "current" metata PDUs in a seperate
        table.
    """
    TABLENAME = "state_pdu"

    def create_from_pdu(pdu):
        return CurrentStatePDUEntry(
                pdu_row_id=pdu.id,
                pdi_context=pdu.context,
                pdu_type=pdu.pdu_type,
                state_key=pdu.key
            )