import os


def schema_path(schema):
    dirPath = os.path.dirname(__file__)
    schemaPath = os.path.join(dirPath, schema + ".sql")
    return schemaPath


def read_schema(schema):
    with open(schema_path(schema)) as schemaFile:
        return schemaFile.read()
