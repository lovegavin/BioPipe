"""Binary VCF (BCF) variant reader using pysam.

Windows native note: pysam has no Windows wheel and pysam source builds need
a C toolchain.  Use WSL/Linux or skip BCF input on native Windows.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import Form, ReaderError
from src.core.contracts import reader_contract
from src.reader.base import Reader
from src.reader.readers._table_common import table_form


class BcfReader(Reader):
    """BCF variant reader; exposes position, quality and allele/sample counts."""

    output_contract = reader_contract()
    file_input = {"dims": ["variant", "field"], "labels": {"variant": "auto", "field": "builtin"}}
    extensions = [".bcf"]
    handles_compression = False
    dependencies = ["pysam>=0.22"]
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
            raise ReaderError(f"BCF reader requires exactly two dims, got {dims}")
        try:
            import pysam
        except ImportError as exc:
            raise ReaderError(
                "BCF reader: pysam is required; use WSL/Linux on Windows"
            ) from exc
        limit = int(args.get("max_records", 100000))
        rows = []
        ids = []
        try:
            with pysam.VariantFile(str(path)) as handle:
                for record in handle:
                    if len(rows) >= limit:
                        break
                    ref = str(record.ref)
                    alt = ",".join(str(a) for a in record.alts or ()) or "."
                    rows.append({
                        "pos": float(record.pos),
                        "qual": float(record.qual) if record.qual is not None else float("nan"),
                        "n_alleles": float(len([ref, *list(record.alts or ())])),
                        "n_samples": float(len(record.samples)),
                    })
                    ids.append(f"{record.chrom}:{record.pos}:{ref}>{alt}")
        except (OSError, ValueError) as exc:
            raise ReaderError(f"BCF reader: cannot parse {path}: {exc}") from exc
        if not rows:
            raise ReaderError("BCF reader: no variant records")
        frame = pd.DataFrame(rows)
        return table_form(
            frame, dims, labels, "BCF",
            encoders_cfg=args.get("encoders") or {},
            row_labels=ids,
            info_extra={"format": "BCF", "n_variants": len(rows)},
        )
