# src/task/step/steps/_annotation_utils.py
"""Shared decoding and interval helpers for GFF-derived genome operators.

The helpers work on the 9-column Form produced by ``GffReader`` (GFF3)
or ``GtfReader`` (GTF).  Operators resolve columns by role so a single
implementation accepts both dialects.
"""
from __future__ import annotations

import re

import numpy as np

from src.core import StepError
from ._annotation_columns import require_role, try_role


_CODONS = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_STOPS = frozenset({"TAA", "TAG", "TGA"})

_ATTRIBUTE_SPLIT = re.compile(r";\s*")


def _decode(column, encoder, step_name):
    if encoder is None:
        raise StepError(
            f"{step_name}: column '{column}' must be encoded before use"
        )
    inverse = encoder.inverse
    return [str(inverse[int(round(float(code)))]) for code in column]


def annotation_table(form, record_dim, field_dim, step_name):
    """Decode a GFF/GTF Form into parallel Python lists."""
    if form.data.ndim != 2 or form.dims[0] != record_dim or form.dims[1] != field_dim:
        raise StepError(
            f"{step_name}: expected 2D [{record_dim},{field_dim}], got {form.dims}"
        )
    labels = form.labels.get(field_dim, {})
    encoders = form.info.get("encoders", {}).get(field_dim, {})

    _, seqid_i, seqid_enc = require_role(labels, encoders, "seqid", step_name)
    _, type_i, type_enc = require_role(labels, encoders, "type", step_name)
    _, start_i, _ = require_role(
        labels, encoders, "start", step_name, require_encoder=False
    )
    _, end_i, _ = require_role(
        labels, encoders, "end", step_name, require_encoder=False
    )

    n = int(form.data.shape[0])
    seqids = _decode(form.data[:, seqid_i], seqid_enc, step_name)
    types = _decode(form.data[:, type_i], type_enc, step_name)
    starts = np.rint(form.data[:, start_i]).astype(np.int64)
    ends = np.rint(form.data[:, end_i]).astype(np.int64)

    strand_role = try_role(labels, encoders, "strand")
    if strand_role[0] is not None:
        strands = _decode(form.data[:, strand_role[1]], strand_role[2], step_name)
    else:
        strands = ["."] * n

    attr_role = try_role(labels, encoders, "attributes")
    if attr_role[0] is not None:
        attributes = _decode(form.data[:, attr_role[1]], attr_role[2], step_name)
    else:
        attributes = [""] * n

    if starts.shape != (n,) or ends.shape != (n,):
        raise StepError(f"{step_name}: start/end columns are not record-parallel")
    if np.any(ends < starts):
        bad = int(np.flatnonzero(ends < starts)[0])
        raise StepError(
            f"{step_name}: record {bad} has end {int(ends[bad])} before start "
            f"{int(starts[bad])}"
        )
    return {
        "seqid": seqids,
        "type": types,
        "start": starts,
        "end": ends,
        "strand": strands,
        "attributes": attributes,
    }


def select_type(table, feature_type, step_name):
    """Indices of records whose third column equals ``feature_type``."""
    chosen = [i for i, name in enumerate(table["type"]) if name == feature_type]
    if not chosen:
        available = sorted(set(table["type"]))
        raise StepError(
            f"{step_name}: no '{feature_type}' records; available types "
            f"{available}"
        )
    return np.asarray(chosen, dtype=np.int64)


def parse_attributes(text):
    """Parse GFF3 ``key=value`` or GTF ``key "value"`` attributes."""
    parsed = {}
    for chunk in _ATTRIBUTE_SPLIT.split(str(text or "")):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "=" in chunk:
            key, value = chunk.split("=", 1)
        elif " " in chunk:
            key, value = chunk.split(" ", 1)
            value = value.strip().strip('"')
        else:
            continue
        parsed[key.strip()] = value.strip().strip('"')
    return parsed


def record_label(attributes, fallback):
    """Prefer a stable gene/CDS identifier over a coordinate string."""
    parsed = parse_attributes(attributes)
    for key in ("locus_tag", "gene_id", "gene", "ID", "Name"):
        value = parsed.get(key)
        if value:
            return str(value)
    return fallback


def unique_labels(labels):
    """Make labels unique without changing the first occurrence of each."""
    seen = {}
    out = []
    for label in labels:
        count = seen.get(label, 0)
        seen[label] = count + 1
        out.append(label if count == 0 else f"{label}#{count + 1}")
    return out

def merge_intervals(intervals):
    """Merge 1-based inclusive intervals; returns sorted disjoint pairs."""
    clean = sorted(
        (int(start), int(end))
        for start, end in intervals
        if int(end) >= int(start)
    )
    merged = []
    for start, end in clean:
        if merged and start <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def complement_intervals(merged, limit, min_length=0):
    """Regions of ``[1, limit]`` not covered by merged 1-based intervals."""
    gaps = []
    cursor = 1
    for start, end in merged:
        if start > cursor:
            gaps.append((cursor, min(start - 1, limit)))
        cursor = max(cursor, end + 1)
        if cursor > limit:
            break
    if cursor <= limit:
        gaps.append((cursor, limit))
    return [
        (start, end)
        for start, end in gaps
        if end >= start and end - start + 1 >= min_length
    ]


def window_overlaps(starts, ends, window_start, window_end):
    """Mask of records intersecting the inclusive window."""
    return (starts <= window_end) & (ends >= window_start)


def reverse_complement(sequence):
    table = str.maketrans("ACGTNacgtn", "TGCANtgcan")
    return str(sequence).translate(table)[::-1]


def translate_dna(sequence):
    """Standard-code translation; ambiguous codons become ``X``."""
    seq = str(sequence).upper().replace("U", "T")
    amino = []
    for offset in range(0, len(seq) - 2, 3):
        amino.append(_CODONS.get(seq[offset:offset + 3], "X"))
    return "".join(amino)


def fasta_sequences(form, sequence_dim, position_dim, step_name):
    """Return ``(names, sequences)`` from a FastaReader Form."""
    if form.data.ndim != 2 or form.dims[0] != sequence_dim or form.dims[1] != position_dim:
        raise StepError(
            f"{step_name}: expected 2D [{sequence_dim},{position_dim}], got {form.dims}"
        )
    sequences = form.info.get("sequences")
    labels = form.labels.get(sequence_dim, {})
    if not isinstance(sequences, (list, tuple)) or len(sequences) != len(labels):
        raise StepError(f"{step_name}: FASTA input lacks info.sequences")
    ordered = sorted(labels.items(), key=lambda item: item[1])
    names = [str(name) for name, _ in ordered]
    return names, [str(sequence) for sequence in sequences]
