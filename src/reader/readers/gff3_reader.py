# src/reader/readers/gff3_reader.py
"""GFF3 (Generic Feature Format version 3) reader.

A 9-column tab-delimited text file. Lines starting with ``#`` are
skipped, and reading stops at an embedded ``##FASTA`` section. Column
names and record semantics are documented on
:class:`src.reader.readers._gff_base._GffLikeReader`.

Reference
---------
GFF3 specification:
https://github.com/The-Sequence-Ontology/Specifications/blob/master/gff3.md
"""
from __future__ import annotations

from ._gff_base import _GffLikeReader


class Gff3Reader(_GffLikeReader):
    """Reader for .gff and .gff3 files."""

    format_name = "GFF3"
    extensions = [".gff", ".gff3"]
    columns = [
        "seqid", "source", "type", "start", "end",
        "score", "strand", "phase", "attributes",
    ]
