# src/reader/readers/txt_reader.py
"""Generic text reader that delegates to another reader.

Handles .txt, .tsv, .tab and similar extensions that have no
dedicated reader. Parsing is delegated to another registered reader,
selected by name.

Params:
    reader : name of the reader to delegate to, matched against the
             class name with "Reader" stripped and lowercased.
             Examples: "csv" -> CsvReader, "bed" -> BedReader,
             "gtf" -> GtfReader. Default "csv".
    All other args are forwarded to the delegated reader.

When the delegate is CsvReader and ``sep`` is not given, a tab
separator is assumed for .txt, .tsv, and .tab files.
"""

from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.reader.base import Reader


class TxtReader(Reader):
    """Read generic text files by delegating to another reader."""

    extensions = [".txt", ".tsv", ".tab"]
    handles_compression = False

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
            if ext in (".tsv", ".tab", ".txt"):
                args["sep"] = "\t"

        return delegate.read(path, dims, labels, **args)


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