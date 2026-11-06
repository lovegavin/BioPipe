"""Shared helpers for alignment-level (MSA) statistics and editing."""

from __future__ import annotations

import math
from collections import Counter

import numpy as np

from src.core import StepError
from ._annotation_utils import fasta_sequences

GAP_CHARS = frozenset("-.")
ALPHABET_SIZES = {"dna": 4, "rna": 4, "protein": 20}
AMBIGUOUS = {"dna": "N", "rna": "N", "protein": "X"}
_RESIDUES = {
    "dna": set("ACGTRYSWKMBDHVN"),
    "rna": set("ACGURYSWKMBDHVN"),
    "protein": set("ACDEFGHIKLMNPQRSTVWYX*"),
}


def alignment_records(form, sequence_dim, position_dim, step_name):
    """Return ``(names, sequences)`` for a gap-preserving alignment Form."""
    names, sequences = fasta_sequences(form, sequence_dim, position_dim, step_name)
    sequences = [str(sequence).upper() for sequence in sequences]
    if len(sequences) < 2:
        raise StepError(f"{step_name}: at least two aligned sequences are required")
    lengths = {len(sequence) for sequence in sequences}
    if len(lengths) != 1:
        raise StepError(
            f"{step_name}: sequences are not aligned; lengths {sorted(lengths)[:5]}"
        )
    if not sequences[0]:
        raise StepError(f"{step_name}: alignment has no columns")
    return names, sequences


def detect_alphabet(sequences):
    characters = set("".join(sequences)) - GAP_CHARS
    for alphabet in ("dna", "rna"):
        if characters <= _RESIDUES[alphabet]:
            return alphabet
    if characters <= _RESIDUES["protein"]:
        return "protein"
    raise StepError(
        f"msa: unsupported alignment characters {sorted(characters)[:8]}"
    )


def resolve_alphabet(sequences, requested):
    alphabet = str(requested).strip().lower()
    if alphabet not in ("auto", "dna", "rna", "protein"):
        raise StepError(f"msa: unknown alphabet {alphabet!r}")
    if alphabet == "auto":
        return detect_alphabet(sequences)
    return alphabet


def column_statistics(sequences, alphabet):
    """Per-column gap fraction, Shannon entropy, conservation and majority."""
    n_sequences = len(sequences)
    n_columns = len(sequences[0])
    h_max = math.log2(ALPHABET_SIZES[alphabet])
    gap_fraction = np.zeros(n_columns, dtype=np.float64)
    entropy = np.zeros(n_columns, dtype=np.float64)
    conservation = np.zeros(n_columns, dtype=np.float64)
    major_fraction = np.zeros(n_columns, dtype=np.float64)
    consensus = []
    for column in range(n_columns):
        values = [sequence[column] for sequence in sequences]
        residues = [value for value in values if value not in GAP_CHARS]
        gap_fraction[column] = 1.0 - len(residues) / n_sequences
        if not residues:
            consensus.append(AMBIGUOUS[alphabet])
            continue
        counts = Counter(residues)
        total = len(residues)
        probabilities = [count / total for count in counts.values()]
        value = -sum(p * math.log2(p) for p in probabilities)
        entropy[column] = value
        conservation[column] = max(0.0, 1.0 - value / h_max)
        residue, count = max(sorted(counts.items()), key=lambda item: item[1])
        major_fraction[column] = count / total
        consensus.append(residue)
    return {
        "gap_fraction": gap_fraction,
        "entropy": entropy,
        "conservation": conservation,
        "major_fraction": major_fraction,
        "consensus": consensus,
    }


def consensus_sequence(stats, alphabet, max_gap_fraction, min_major_fraction):
    ambiguous = AMBIGUOUS[alphabet]
    characters = []
    for index in range(len(stats["gap_fraction"])):
        if (
            stats["gap_fraction"][index] > max_gap_fraction
            or stats["major_fraction"][index] < min_major_fraction
        ):
            characters.append(ambiguous)
        else:
            characters.append(stats["consensus"][index])
    return "".join(characters)


def identity_matrix(sequences):
    n_sequences = len(sequences)
    matrix = np.zeros((n_sequences, n_sequences), dtype=np.float64)
    comparable = np.zeros((n_sequences, n_sequences), dtype=np.int64)
    for i in range(n_sequences):
        for j in range(i + 1, n_sequences):
            pairs = [
                (left, right)
                for left, right in zip(sequences[i], sequences[j])
                if left not in GAP_CHARS and right not in GAP_CHARS
            ]
            both = len(pairs)
            same = sum(1 for left, right in pairs if left == right)
            comparable[i, j] = comparable[j, i] = both
            value = same / both if both else 0.0
            matrix[i, j] = matrix[j, i] = value
    np.fill_diagonal(matrix, 1.0)
    return matrix, comparable


def trim_alignment(names, sequences, max_gap_fraction, min_row_fraction):
    n_sequences = len(sequences)
    n_columns = len(sequences[0])
    gap_fraction = np.asarray(
        [
            sum(1 for sequence in sequences if sequence[column] in GAP_CHARS) / n_sequences
            for column in range(n_columns)
        ],
        dtype=np.float64,
    )
    keep_columns = [
        column for column in range(n_columns) if gap_fraction[column] <= max_gap_fraction
    ]
    if not keep_columns:
        raise StepError("msa_trim: every column exceeds the gap fraction threshold")
    kept_names = []
    kept_sequences = []
    removed_rows = 0
    for name, sequence in zip(names, sequences):
        trimmed = "".join(sequence[column] for column in keep_columns)
        called = sum(1 for character in trimmed if character not in GAP_CHARS)
        if called / len(keep_columns) >= min_row_fraction:
            kept_names.append(name)
            kept_sequences.append(trimmed)
        else:
            removed_rows += 1
    if not kept_sequences:
        raise StepError("msa_trim: no row meets the row coverage threshold")
    kept_gap = sum(
        1
        for sequence in kept_sequences
        for character in sequence
        if character in GAP_CHARS
    )
    return {
        "names": kept_names,
        "sequences": kept_sequences,
        "columns_before": n_columns,
        "columns_after": len(keep_columns),
        "columns_removed": n_columns - len(keep_columns),
        "rows_before": n_sequences,
        "rows_after": len(kept_sequences),
        "rows_removed": removed_rows,
        "gap_fraction_before": float(gap_fraction.mean()),
        "gap_fraction_after": kept_gap / (len(kept_sequences) * len(keep_columns)),
    }
