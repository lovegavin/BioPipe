# src/reader/readers/gtf_reader.py
"""GTF (Gene Transfer Format) reader.

A 9-column tab-delimited text file. Lines starting with ``#`` are
skipped, and reading stops at an embedded ``##FASTA`` section. Column
names and record semantics are documented on
:class:`src.reader.readers._gff_base._GffLikeReader`.

Reference
---------
GTF specification:
https://www.ensembl.org/info/website/upload/gff.html
"""
from __future__ import annotations

from ._gff_base import _GffLikeReader


class GtfReader(_GffLikeReader):
    """Reader for .gtf files."""

    format_name = "GTF"
    extensions = [".gtf"]
    columns = [
        "seqname", "source", "feature", "start", "end",
        "score", "strand", "frame", "attribute",
    ]
