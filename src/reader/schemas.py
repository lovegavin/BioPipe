"""Declarative options for built-in readers, available without optional parsers."""
from copy import deepcopy


def builtin_schema(name):
    encoder = {
        "type": "object",
        "title": "Encoders",
        "description": "Per-field encoder configuration.",
        "additionalProperties": True,
    }
    csv = {
        "header": {
            "type": "boolean",
            "title": "Header row",
            "default": True,
        },
        "sep": {
            "type": "string",
            "title": "Separator",
            "minLength": 1,
        },
        "encoders": encoder,
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Columns",
            "description": (
                "Restrict the reader to these header names, in order. "
                "Label indices still refer to the original file."
            ),
        },
        "info_columns": {
            "type": "object",
            "title": "Info columns",
            "description": (
                "Map a header name to an info field. The column is "
                "read as strings into info[field] and declared "
                "parallel to the row dimension."
            ),
            "additionalProperties": {"type": "string"},
        },
    }
    tsv = {
        "header": {
            "type": "boolean",
            "title": "Header row",
            "default": True,
        },
        "encoders": encoder,
        "columns": {
            "type": "array",
            "items": {"type": "string"},
            "title": "Columns",
            "description": (
                "Restrict the reader to these header names, in order. "
                "Label indices still refer to the original file."
            ),
        },
        "info_columns": {
            "type": "object",
            "title": "Info columns",
            "description": (
                "Map a header name to an info field. The column is "
                "read as strings into info[field] and declared "
                "parallel to the row dimension."
            ),
            "additionalProperties": {"type": "string"},
        },
    }
    definitions = {
        "CsvReader": csv,
        "TsvReader": tsv,
        "TxtReader": {
            **csv,
            "reader": {
                "type": "string",
                "title": "Delegate reader",
                "default": "csv",
            },
        },
        "H5adReader": {
            "layer": {
                "type": ["string", "null"],
                "x-ui-type": "string",
                "title": "Layer",
                "description": "Leave unset to read X.",
            },
        },
        **{
            key: {"encoders": encoder}
            for key in ("BedReader", "GtfReader", "Gff3Reader", "ParquetReader")
        },
    }
    return {
        "type": "object",
        "properties": deepcopy(definitions.get(name, {})),
        "additionalProperties": True,
    }