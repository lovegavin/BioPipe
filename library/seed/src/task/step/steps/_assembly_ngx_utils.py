"""Shared helpers for assembly completeness (NGx) operators."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError


def contig_lengths(records):
    lengths = [len(sequence) for _, sequence in records]
    if not lengths:
        raise StepError("assembly: no contigs found")
    return np.asarray(lengths, dtype=np.int64)


def sorted_lengths(lengths):
    return np.sort(np.asarray(lengths, dtype=np.int64))[::-1]


def cumulative(lengths):
    return np.cumsum(sorted_lengths(lengths))


def threshold_for(lengths, target):
    """Contig length at which the cumulative length first reaches ``target``."""
    ordered = np.asarray(lengths, dtype=np.float64)
    if ordered.size == 0:
        return 0.0
    if target <= 0:
        return float(ordered[0])
    cumulative = np.cumsum(ordered)
    position = int(np.searchsorted(cumulative, target, side="left"))
    if position >= ordered.size:
        position = ordered.size - 1
    return float(ordered[position])


def ngx(lengths, genome_size, x):
    target = float(genome_size) * float(x) / 100.0
    return threshold_for(sorted_lengths(lengths), target)


def aux(lengths, total, x):
    target = float(total) * float(x) / 100.0
    return threshold_for(sorted_lengths(lengths), target)


def au_n(lengths, denominator):
    ordered = np.asarray(lengths, dtype=np.float64)
    if denominator <= 0:
        return 0.0
    return float(np.sum(ordered * ordered) / float(denominator))


def n50_l50(lengths, total):
    ordered = sorted_lengths(lengths)
    target = float(total) / 2.0
    position = int(np.searchsorted(np.cumsum(ordered), target, side="left"))
    if position >= ordered.size:
        position = ordered.size - 1
    return float(ordered[position]), position + 1


def curve_rows(lengths, genome_size, step):
    ordered = sorted_lengths(lengths)
    running = np.cumsum(ordered)
    total = float(running[-1])
    rows = []
    for x in range(step, 101, step):
        target = float(genome_size) * float(x) / 100.0
        position = int(np.searchsorted(running, target, side="left"))
        if position >= ordered.size:
            position = ordered.size - 1
        rows.append(
            (
                float(x),
                float(ordered[position]),
                int(position + 1),
                float(running[position] / total) if total else 0.0,
                float(running[position] / float(genome_size)) if genome_size else 0.0,
            )
        )
    return rows


def bin_edges(text):
    values = []
    for token in str(text).replace(";", ",").split(","):
        token = token.strip()
        if not token:
            continue
        try:
            value = int(float(token))
        except ValueError as exc:
            raise StepError(f"assembly_length_bins: invalid edge {token!r}") from exc
        if value < 0:
            raise StepError("assembly_length_bins: edges must be non-negative")
        values.append(value)
    if len(values) < 2:
        raise StepError("assembly_length_bins: at least two edges are required")
    values = sorted(set(values))
    if values[-1] != 0:
        values.append(0)
    return values


def bin_rows(lengths, edges):
    rows = []
    for index in range(len(edges) - 1):
        low = edges[index]
        high = edges[index + 1]
        if high == 0:
            selected = lengths[lengths >= low]
            label = f">={low}"
        else:
            selected = lengths[(lengths >= low) & (lengths < high)]
            label = f"{low}-{high - 1}" if high - low > 1 else str(low)
        rows.append((label, int(selected.size), int(selected.sum()), int(selected.max()) if selected.size else 0))
    return rows
