"""Shared helpers for assembly quality-control operators."""

from __future__ import annotations

import numpy as np

from src.core import StepError
from ._annotation_utils import fasta_sequences


def contig_records(form, sequence_dim, position_dim, step_name):
    """Return ``[(name, sequence)]`` in label order from a FASTA Form."""
    names, sequences = fasta_sequences(form, sequence_dim, position_dim, step_name)
    if not names:
        raise StepError(f"{step_name}: FASTA input is empty")
    return list(zip(names, [sequence.upper() for sequence in sequences]))


def composition(sequence):
    """Return (gc, n_bases, length) for one contig."""
    text = str(sequence)
    upper = text.upper()
    gc = upper.count("G") + upper.count("C")
    n_bases = upper.count("N")
    return gc, n_bases, len(text)


def gap_runs(sequence):
    """Return [(start, end)] half-open runs of N/n bases."""
    runs = []
    start = None
    for index, base in enumerate(str(sequence).upper()):
        if base == "N":
            if start is None:
                start = index
        elif start is not None:
            runs.append((start, index))
            start = None
    if start is not None:
        runs.append((start, len(sequence)))
    return runs


def contiguity(lengths):
    """Compute N/L statistics for a list of contig lengths."""
    values = [int(value) for value in lengths if int(value) > 0]
    if not values:
        raise StepError("assembly_contiguity: no positive contig lengths")
    total = sum(values)
    ordered = sorted(values, reverse=True)
    cumulative = np.cumsum(ordered)

    def n_at(fraction):
        target = total * fraction
        index = int(np.searchsorted(cumulative, target, side="left"))
        index = min(index, len(ordered) - 1)
        return ordered[index], index + 1

    n50, l50 = n_at(0.5)
    n90, l90 = n_at(0.9)
    aun = sum(value * value for value in ordered) / total
    return {
        "n_contigs": len(ordered),
        "total_bp": total,
        "min_length": min(ordered),
        "max_length": max(ordered),
        "mean_length": total / len(ordered),
        "median_length": float(np.median(ordered)),
        "n50": n50,
        "l50": l50,
        "n90": n90,
        "l90": l90,
        "aun": aun,
        "gc_fraction": None,
    }
