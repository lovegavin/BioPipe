"""NEXUS alignment reader.

Reads a simple NEXUS DATA block with a non-interleaved MATRIX. The
matrix may contain DNA or protein characters; gaps become NaN and
unknown characters use code 5.
"""
from __future__ import annotations

from pathlib import Path

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._alignment_common import alignment_form, read_nexus


class NexusReader(Reader):
    """Reader for .nex / .nexus alignments."""

    output_contract = reader_contract()
    file_input = {"dims": ["sequence", "position"], "labels": {"sequence": "builtin", "position": "auto"}}
    extensions = [".nex", ".nexus"]
    handles_compression = False
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def read(self, path: Path, dims: list, labels: dict, **args):
        ids, seqs = read_nexus(path)
        if not ids:
            raise ReaderError("Nexus reader: no MATRIX sequences found")
        return alignment_form(ids, seqs, dims, labels, "nexus")
