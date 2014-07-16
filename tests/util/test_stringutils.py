# -*- coding: utf-8 -*-
from synapse.util.stringutils import JSONTemplate

import unittest


class JsonTemplateTestCase(unittest.TestCase):

    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_top_level_keys(self):
        template = {
            "person": {},
            "friends": []
        }
        t = JSONTemplate(template)

        content = {
            "person": {"name": "bob"},
            "friends": ["jill", "mike"]
        }

        self.assertTrue(t.check_json(content, raises=False))

        content = {
            "person": {"name": "bob"},
            "friends": ["jill"],
            "enemies": ["mike"]
        }
        self.assertTrue(t.check_json(content, raises=False))

        content = {
            "person": {"name": "bob"},
            # missing friends
            "enemies": ["mike", "jill"]
        }
        self.assertFalse(t.check_json(content, raises=False))

    def test_nested_keys(self):
        template = {
            "person": {
                "attributes": {
                    "hair": "string",
                    "eye": "string"
                },
                "age": 0,
                "fav_books": []
            }
        }
        t = JSONTemplate(template)

        content = {
            "person": {
                "attributes": {
                    "hair": "brown",
                    "eye": "green",
                    "skin": "purple"
                },
                "age": 33,
                "fav_books": ["lotr", "hobbit"],
                "fav_music": ["abba", "beatles"]
            }
        }

        self.assertTrue(t.check_json(content, raises=False))

        content = {
            "person": {
                "attributes": {
                    "hair": "brown"
                    # missing eye
                },
                "age": 33,
                "fav_books": ["lotr", "hobbit"],
                "fav_music": ["abba", "beatles"]
            }
        }

        self.assertFalse(t.check_json(content, raises=False))

        content = {
            "person": {
                "attributes": {
                    "hair": "brown",
                    "eye": "green",
                    "skin": "purple"
                },
                "age": 33,
                "fav_books": "nothing", # should be a list
            }
        }

        self.assertFalse(t.check_json(content, raises=False))

