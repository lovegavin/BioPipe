"""BAM alignment reader using pysam.

Output is one row per alignment and numeric alignment fields; read names
are kept as the row labels.  An index is not required for sequential reads.
"""
from __future__ import annotations

from pathlib import Path

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._bam_common import alignment_frame
from src.reader.readers._table_common import table_form


class BamReader(Reader):
    """Binary Alignment/Map reader."""

    output_contract = reader_contract()
    file_input = {"dims": ["read", "field"], "labels": {"read": "auto", "field": "builtin"}}
    extensions = [".bam"]
    platforms = ["linux", "darwin"]
    handles_compression = False
    dependencies = ["pysam"]
    dependency_imports = ["pysam"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_records": {"type": "integer", "minimum": 1, "default": 100000},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BAM reader requires exactly two dims, got {dims}")
        frame = alignment_frame(path, "BAM", int(args.get("max_records", 100000)))
        return table_form(
            frame.drop(columns=["qname"]), dims, labels, "BAM",
            encoders_cfg=args.get("encoders") or {},
            row_labels=frame["qname"].tolist(),
            info_extra={"format": "BAM"},
        )
