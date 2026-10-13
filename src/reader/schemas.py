"""Declarative options for built-in readers, available without optional parsers."""
from copy import deepcopy


def builtin_schema(name):
    encoder = {"type": "object", "title": "Encoders", "description": "Per-field encoder configuration.", "additionalProperties": True}
    csv = {"header": {"type": "boolean", "title": "Header row", "default": True},
           "sep": {"type": "string", "title": "Separator", "minLength": 1},
           "encoders": encoder}
    definitions = {
        "CsvReader": csv,
        "TxtReader": {**csv, "reader": {"type": "string", "title": "Delegate reader", "default": "csv"}},
        "H5adReader": {"layer": {"type": ["string", "null"], "x-ui-type": "string", "title": "Layer", "description": "Leave unset to read X."}},
        **{key: {"encoders": encoder} for key in ("BedReader", "GtfReader", "Gff3Reader", "ParquetReader")},
    }
    return {"type": "object", "properties": deepcopy(definitions.get(name, {})), "additionalProperties": True}
