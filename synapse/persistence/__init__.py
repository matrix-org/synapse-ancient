# -*- coding: utf-8 -*-
"""This package is resposible for querying the databases used for persisting
data.
"""
import os


def schema_path(schema):
    """ Get a filesystem path for the named database schema

    Args:
        schema: Name of the database schema.
    Returns:
        A filesystem path pointing at a ".sql" file.

    """
    dir_path = os.path.dirname(__file__)
    schemaPath = os.path.join(dir_path, "schema", schema + ".sql")
    return schemaPath


def read_schema(schema):
    """ Read the named database schema.

    Args:
        schema: Name of the datbase schema.
    Returns:
        A string containing the database schema.
    """
    with open(schema_path(schema)) as schema_file:
        return schema_file.read()
