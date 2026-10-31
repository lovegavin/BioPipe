"""BigWig interval reader using pyBigWig."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BigWigReader(Reader):
    """Reader for .bw / .bigwig coverage tracks."""

    output_contract = reader_contract()
    file_input = {"dims": ["region", "field"], "labels": {"region": "auto", "field": "builtin"}}
    extensions = [".bw", ".bigwig"]
    platforms = ["linux", "darwin"]
    handles_compression = False
    dependencies = ["pyBigWig"]
    dependency_imports = ["pyBigWig"]
    parameters_schema = {
        "type": "object",
        "properties": {
            "max_records": {"type": "integer", "minimum": 1, "default": 100000},
            "chrom": {"type": "string"},
            "encoders": {"type": "object", "additionalProperties": True},
        },
        "additionalProperties": False,
    }

    def read(self, path: Path, dims: list, labels: dict, **args) -> Form:
        if len(dims) != 2:
            raise ReaderError(f"BigWig reader requires exactly two dims, got {dims}")
        try:
            import pyBigWig
        except ImportError as exc:
            raise ReaderError("BigWig reader requires pyBigWig") from exc
        max_records = int(args.get("max_records", 100000))
        if max_records < 1:
            raise ReaderError("BigWig reader: max_records must be >= 1")
        handle = pyBigWig.open(str(path))
        if handle is None:
            raise ReaderError(f"BigWig reader: cannot open {path}")
        try:
            chroms = handle.chroms()
            wanted = args.get("chrom")
            chosen = [wanted] if wanted else list(chroms)
            if wanted and wanted not in chroms:
                raise ReaderError(f"BigWig reader: chromosome {wanted!r} not present")
            rows = []
            names = []
            for chrom in chosen:
                if len(rows) >= max_records:
                    break
                intervals = handle.intervals(chrom) or ()
                for start, end, value in intervals:
                    if len(rows) >= max_records:
                        break
                    rows.append([chrom, int(start), int(end), float(value)])
                    names.append(f"{chrom}:{start}-{end}")
            if not rows:
                raise ReaderError("BigWig reader: no intervals")
            frame = pd.DataFrame(rows, columns=["chrom", "start", "end", "value"])
            return table_form(
                frame, dims, labels, "BigWig",
                encoders_cfg=args.get("encoders") or {},
                row_labels=names,
                info_extra={"format": "BigWig"},
            )
        finally:
            handle.close()
