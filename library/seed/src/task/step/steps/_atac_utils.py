"""Shared helpers for the ATAC-seq QC operators.

Fragments are reconstructed from paired BAM records: only the left read of a
pair (positive template length) contributes, so every fragment is counted
once.  BED inputs are decoded through the Form encoders, which keeps the
operators independent of whether the reader stored names as strings or codes.
"""
from __future__ import annotations

from src.core import StepError
from src.task.step.steps._bam_utils import iter_records, read_header


def bam_path(artifact, operator: str) -> str:
    """Validate a BAM FileArtifact and return its path."""
    from src.core import FileArtifact

    if not isinstance(artifact, FileArtifact) or artifact.format != 'bam':
        raise StepError(f'{operator} requires a BAM file artifact')
    artifact.validate()
    return next(iter(artifact.files.values()))


def reference_names(path: str) -> list:
    _, references = read_header(path)
    return [name for name, _length in references]


def iter_fragments(path: str, min_mapq: int = 30, max_records: int = 0,
                   exclude_duplicates: bool = True, proper_pair: bool = False):
    """Yield (reference, start, end) for each usable paired fragment."""
    names = reference_names(path)
    seen = 0
    for record in iter_records(path):
        flag = record["flag"]
        if flag & 0x4 or flag & 0x100 or flag & 0x800:
            continue
        if exclude_duplicates and flag & 0x400:
            continue
        if proper_pair and not flag & 0x2:
            continue
        if not flag & 0x1:
            continue
        if record["mapq"] < min_mapq:
            continue
        tlen = record["tlen"]
        if tlen <= 0:
            continue
        ref_id = record["ref_id"]
        if ref_id < 0 or ref_id >= len(names):
            continue
        start = record["pos"]
        yield names[ref_id], start, start + tlen
        seen += 1
        if max_records and seen >= max_records:
            break


def _column(form, field_dim: str, name: str, row: int):
    labels = form.labels[field_dim]
    if name not in labels:
        raise StepError(f"BED input is missing column '{name}'")
    index = labels[name]
    value = form.data[row, index]
    encoders = (form.info or {}).get("encoders", {}).get(field_dim, {})
    encoder = encoders.get(name) if isinstance(encoders, dict) else None
    if encoder is not None:
        return encoder.inverse[int(round(float(value)))]
    return value


def bed_records(form, region_dim: str = "region", field_dim: str = "field",
                chrom_field: str = "chrom", start_field: str = "chromStart",
                end_field: str = "chromEnd", strand_field: str = "strand"):
    """Decode a BED Form into a list of (chrom, start, end, strand)."""
    for dim in (region_dim, field_dim):
        if dim not in form.dims:
            raise StepError(f"BED input does not have dim '{dim}'")
    rows = []
    for row in range(form.data.shape[0]):
        chrom = str(_column(form, field_dim, chrom_field, row))
        start = int(round(float(_column(form, field_dim, start_field, row))))
        end = int(round(float(_column(form, field_dim, end_field, row))))
        if end < start:
            raise StepError(f"BED row {row} has end {end} before start {start}")
        strand = "+"
        labels = form.labels[field_dim]
        if strand_field in labels:
            strand = str(_column(form, field_dim, strand_field, row))
        rows.append((chrom, start, end, strand))
    return rows
