"""CRAM alignment reader using pysam.

A reference FASTA must be supplied as ``reference`` because CRAM stores
alignments relative to a reference sequence.
"""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._bam_common import alignment_frame
from src.reader.readers._table_common import table_form


class CramReader(Reader):
    """Compressed Reference-oriented Alignment/Map reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["read", "field"], "labels": {"read": "auto", "field": "builtin"}}
    extensions = [".cram"]
    platforms = ["linux", "darwin"]
    handles_compression = False
    dependencies = ["pysam"]
    dependency_imports = ["pysam"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "reference": {"type": "string"},
            "max_records": {"type": "integer", "minimum": 1, "default": 100000},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"CRAM reader requires exactly two dims, got {dims}")
        reference = args.get("reference")
        frame = alignment_frame(path, "CRAM", int(args.get("max_records", 100000)), reference=reference)
        return table_form(
            frame.drop(columns=["qname"]), dims, labels, "CRAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=frame["qname"].tolist(),
            info_extra={"format": "CRAM", "reference": str(reference)},
        )
