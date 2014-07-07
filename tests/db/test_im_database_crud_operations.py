""" Unit tests the database layer with test data. This does actual database operations on a test database. """
# twisted imports
from twisted.internet.defer import Deferred
from twisted.internet import defer

# twistar imports
from twistar.dbobject import DBObject

# trial imports
from twisted.trial import unittest

# synapse imports
from synapse.db import schema_path
from synapse.db.database import Database
from synapse.api.messages import Message
from synapse.api.core import SynapseApi

# python imports
from mock import patch, Mock
import os

SCHEMA_SQL = schema_path("im")
TEST_DB = "_temp.db"

def _remove_db():
    global TEST_DB
    try:
        os.remove(TEST_DB)
    except OSError:
        pass

class DatabaseSetupTestCase(unittest.TestCase):
    """ Checks that the database can read schemas and setup a database. """

    def setUp(self):
        pass

    def tearDown(self):
        _remove_db()

    def test_database_setup(self):
        global SCHEMA_SQL
        global TEST_DB
        # find and load the schema. This is a little naughty since we are assuming
        # where the schema folder is. We assume that these tests are being run from
        # _trial_temp and therefore the schema folder is a directory up.
        self.assertTrue(os.path.exists(SCHEMA_SQL), msg="Cannot find %s. Execution directory: %s"%(SCHEMA_SQL,os.getcwd()))

        self.database = Database(TEST_DB)
        d = self.database.init_from_file(SCHEMA_SQL, TEST_DB)

        def _cb(db_setup):
            self.assertTrue(db_setup, "Database unexpectedly already exists.")
        d.addCallback(_cb)
        return d

    def test_database_setup_failure_no_schema(self):
        global TEST_DB
        database = Database(TEST_DB)
        d = database.init_from_file("some_bogus_file.sql", TEST_DB)
        self.assertFailure(d, IOError)
        return d

    def test_database_setup_failure_malformed_schema(self):
        global TEST_DB
        malformed = "malformed.sql"
        with open(malformed, "w") as mal:
            mal.write("CREATE TABLE boo VALUES (aaa,bbb,cc); CREATE TABLE IF NOT EXISTS BLARGH")

        database = Database(TEST_DB)
        d = database.init_from_file(malformed, TEST_DB)
        self.assertFailure(d, SyntaxError)
        return d

    def test_database_setup_failure_db_exists(self):
        global SCHEMA_SQL
        global TEST_DB
        # touch the file
        open(TEST_DB, 'a').close()

        database = Database(TEST_DB)
        d = database.init_from_file(SCHEMA_SQL, TEST_DB)

        def _cb(db_setup):
            self.assertFalse(db_setup, "Database unexpectedly didn't exist.")
        d.addCallback(_cb)
        return d

class DatabaseCrudTestCase(unittest.TestCase):
    """ Checks that the database can perform CRUD operations on data. """

    def setUp(self):
        global SCHEMA_SQL
        global TEST_DB
        self.database = Database(TEST_DB)
        d = self.database.init_from_file(SCHEMA_SQL, TEST_DB)
        self.database.make_default_db_pool()
        return d

    def tearDown(self):
        _remove_db()

    @defer.inlineCallbacks
    def test_crud_message(self):
        # CREATE
        msg = Message(sender_synid="s@syn.org", body="hello", type=Message.TEXT)
        yield msg.save()

        # READ
        msgs = yield Message.findBy(sender_synid="s@syn.org")
        self.assertEquals("hello", msgs[0].body)

        # UPDATE
        msgs[0].body = "goodbye"
        def _cb(updated_msg): # verify
            self.assertEquals("goodbye",updated_msg.body)
        yield msgs[0].save().addCallback(_cb)

        # DELETE
        yield msgs[0].delete()
        msgs = yield Message.findBy(sender_synid="s@syn.org") # verify
        self.assertEquals(0, len(msgs))

class DatabaseVersionQueriesTestCase(unittest.TestCase):
    """ Checks that the correct data is pulled out for a given version. """

    BOOTSTRAP_SQL = os.path.join(os.path.dirname(__file__), "test.sql") # tests execute in tests/_trial_temp

    def _test_create_db(self):
        global SCHEMA_SQL
        global TEST_DB
        self.database = Database(TEST_DB)
        d = self.database.init_from_file(SCHEMA_SQL, TEST_DB)
        self.database.make_default_db_pool()
        return d

    @defer.inlineCallbacks
    def setUp(self):
        yield self._test_create_db()
        bootstrap = open(DatabaseVersionQueriesTestCase.BOOTSTRAP_SQL,'r')
        yield self.database.execute_statements(bootstrap.read())

    def tearDown(self):
        _remove_db()

    @defer.inlineCallbacks
    def test_get_from_invalid_versions(self):
        # no room
        msgs = yield self.database.get_messages(from_version=3, room_id="noroom")
        self.assertEquals(0, len(msgs))

        # version too high
        msgs = yield self.database.get_messages(from_version=7)
        self.assertEquals(0, len(msgs))

        # cannot have to= without from=
        self.assertRaises(IndexError, self.database.get_messages, to_version=4)


    @defer.inlineCallbacks
    def test_get_from_versions(self):
        # get from version (e.g. streaming)
        msgs = yield self.database.get_messages(from_version=3, room_id="room2")
        self.assertEquals(2, len(msgs))
        self.assertEquals("sup", msgs[0].body)
        self.assertEquals("waz goin on", msgs[1].body)
        self.assertEquals(4, msgs[0].id)
        self.assertEquals(5, msgs[1].id)

        # get from= and to= (e.g. paginating a hole) BACKWARDS
        msgs = yield self.database.get_messages(from_version=5, to_version=2, room_id="room2")
        self.assertEquals(2, len(msgs))
        self.assertEquals(4, msgs[0].id)
        self.assertEquals(3, msgs[1].id)

        # get from= and to= FORWARDS
        msgs = yield self.database.get_messages(from_version=2, to_version=5, room_id="room2")
        self.assertEquals(2, len(msgs))
        self.assertEquals(3, msgs[0].id)
        self.assertEquals(4, msgs[1].id)

        # get latest entry (e.g. most recent room member state)
        member = yield self.database.get_room_membership(room_id="room2", synid="z@syn.org")
        self.assertEquals("left", member.state)

        # TODO get previous messages from version (e.g. last 3 messages with feedback)

        # limit testing
        msg = yield self.database.get_messages(from_version=5, to_version=1, room_id="room2", limit=1)
        self.assertEquals(4, msg.id)



