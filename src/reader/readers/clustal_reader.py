"""Clustal alignment reader.

Parses CLUSTAL/MUSCLE block alignments into a sequence x position
numeric matrix. Gaps (``-`` and ``.``) become NaN; nucleotides use the
same codes as the FASTA reader.
"""
from __future__ import annotations

from pathlib import Path

from src.core import ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._alignment_common import alignment_form, read_clustal


class ClustalReader(Reader):
    """Reader for .aln / .clustal block alignments."""

    output_contract = reader_contract()
    file_input = {"dims": ["sequence", "position"], "labels": {"sequence": "builtin", "position": "auto"}}
    extensions = [".aln", ".clustal"]
    handles_compression = False
    parameters_schema = {"type": "object", "properties": {}, "additionalProperties": False}

    def read(self, path: Path, dims: list, labels: dict, **args):
        ids, seqs = read_clustal(path)
        if not ids:
            raise ReaderError("Clustal reader: no aligned sequences found")
        return alignment_form(ids, seqs, dims, labels, "clustal")
