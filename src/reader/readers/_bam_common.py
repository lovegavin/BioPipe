"""Shared alignment reader helpers for BAM and CRAM."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.core import ReaderError

FIELDS = [
    "flag", "reference_id", "reference_start", "mapping_quality",
    "cigar_units", "query_length", "template_length", "next_reference_id",
    "next_reference_start", "query_alignment_length", "is_paired",
    "is_unmapped", "is_reverse", "is_secondary", "is_supplementary",
]


def alignment_frame(path: Path, format_name: str, max_records: int, reference: str | None = None) -> pd.DataFrame:
    if max_records < 1:
        raise ReaderError(f"{format_name} reader: max_records must be >= 1")
    try:
        import pysam
    except ImportError as exc:
        raise ReaderError(f"{format_name} reader requires pysam") from exc
    if format_name == "CRAM" and not reference:
        raise ReaderError("CRAM reader requires a 'reference' FASTA path")
    kwargs = {}
    if reference:
        kwargs["reference_filename"] = str(reference)
    mode = "rc" if format_name == "CRAM" else "rb"
    rows = []
    names = []
    try:
        handle = pysam.AlignmentFile(str(path), mode, **kwargs)
    except Exception as exc:
        raise ReaderError(f"{format_name} reader: cannot open {path}: {exc}") from exc
    with handle:
        for record in handle:
            if len(rows) >= max_records:
                break
            cigars = record.cigartuples or []
            rows.append([
                int(record.flag), int(record.reference_id), int(record.reference_start),
                int(record.mapping_quality), len(cigars), int(record.query_length),
                int(record.template_length), int(record.next_reference_id),
                int(record.next_reference_start), int(record.query_alignment_length),
                int(record.is_paired), int(record.is_unmapped), int(record.is_reverse),
                int(record.is_secondary), int(record.is_supplementary),
            ])
            names.append(record.query_name or f"read:{len(rows) - 1}")
    if not rows:
        raise ReaderError(f"{format_name} reader: no alignment records")
    frame = pd.DataFrame(rows, columns=FIELDS)
    frame.insert(0, "qname", names)
    return frame
