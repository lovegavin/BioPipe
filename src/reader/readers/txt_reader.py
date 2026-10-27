# src/reader/readers/txt_reader.py
"""Generic text reader that delegates to another reader.

Handles .txt and .tab extensions that have no dedicated reader.
Parsing is delegated to another registered reader, selected by name.

Params:
    reader : name of the reader to delegate to, matched against the
             class name with "Reader" stripped and lowercased.
             Examples: "csv" -> CsvReader, "bed" -> BedReader,
             "gtf" -> GtfReader. Default "csv".
    All other args are forwarded to the delegated reader.

When the delegate is CsvReader and ``sep`` is not given, a tab
separator is assumed for .txt and .tab files.
"""

from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader
from src.core.contracts import reader_contract, validate_form, validate_output, source_schema


class TxtReader(Reader):
    """Read generic text files by delegating to another reader."""

    # The delegate owns dimensionality and format-specific metadata guarantees.
    output_contract = {**reader_contract(ndim=None), "info_open": True}

    file_input = {'dims': ['sample', 'feature'], 'labels': {'sample': 'auto', 'feature': 'builtin'}}

    extensions = [".txt", ".tab"]
    handles_compression = False
    parameters_schema = {
        "type": "object",
        "properties": {
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
            "encoders": {
                "type": "object",
                "title": "Encoders",
                "description": "Per-field encoder configuration.",
                "additionalProperties": True,
            },
            "columns": {
                "type": "array",
                "items": {"type": "string"},
                "title": "Columns",
                "description": "Restrict the reader to these header names, in order. Label indices still refer to the original file.",
            },
            "info_columns": {
                "type": "object",
                "title": "Info columns",
                "description": "Map a header name to an info field. The column is read as strings into info[field] and declared parallel to the row dimension.",
                "additionalProperties": {"type": "string"},
            },
            "reader": {
                "type": "string",
                "title": "Delegate reader",
                "default": "csv",
            },
        },
        "additionalProperties": True,
    }


    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        reader_name = args.pop("reader", "csv")
        if not isinstance(reader_name, str):
            raise ReaderError(
                f"TxtReader: 'reader' must be a string, "
                f"got {type(reader_name).__name__}"
            )

        delegate = _find_reader(reader_name, exclude=self)

        # Sensible default separator for the CSV delegate.
        if type(delegate).__name__ == "CsvReader" and "sep" not in args:
            ext = path.suffix.lower()
            if ext in (".tab", ".txt"):
                args["sep"] = "\t"

        form = delegate.read(path, dims, labels, **args)
        validate_form(form, delegate.output_contract, f"TxtReader/{type(delegate).__name__} output")
        validate_output(form, source_schema(delegate.output_contract, dims), f"TxtReader/{type(delegate).__name__} output")
        return form


def _find_reader(name: str, exclude: Reader | None = None) -> Reader:
    from src.reader import READERS

    key = name.lower().strip()
    matches: list[Reader] = []
    for r in READERS:
        if r is exclude:
            continue
        cls_name = type(r).__name__
        stem = cls_name[:-len("Reader")] if cls_name.endswith("Reader") \
            else cls_name
        if stem.lower() == key:
            matches.append(r)

    if not matches:
        available = sorted({
            (lambda c: c[:-len("Reader")] if c.endswith("Reader") else c)(
                type(r).__name__
            ).lower()
            for r in READERS
            if r is not exclude
        })
        raise ReaderError(
            f"TxtReader: no reader named '{name}'. "
            f"Available: {available}"
        )
    if len(matches) > 1:
        raise ReaderError(
            f"TxtReader: ambiguous reader name '{name}': "
            f"{[type(r).__name__ for r in matches]}"
        )
    return matches[0]