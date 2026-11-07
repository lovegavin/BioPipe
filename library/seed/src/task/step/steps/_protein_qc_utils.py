"""Shared helpers for protein quality-control metrics."""
from __future__ import annotations

from src.core import StepError

from ._diwv_table import AA20, DIWV

_INDEX = {aa: i for i, aa in enumerate(AA20)}

# Average residue masses (Da), IUPAC values used by Biopython/ProtParam.
_MASS = {
    "A": 89.0932, "C": 121.1582, "D": 133.1027, "E": 147.1293,
    "F": 165.1891, "G": 75.0666, "H": 155.1546, "I": 131.1729,
    "K": 146.1876, "L": 131.1729, "M": 149.2113, "N": 132.1179,
    "P": 115.1305, "Q": 146.1445, "R": 174.2010, "S": 105.0926,
    "T": 119.1192, "V": 117.1463, "W": 204.2252, "Y": 181.1885,
}
_WATER = 18.0153


def clean_sequence(sequence: str, operator: str) -> str:
    """Uppercase and strip whitespace; reject residues outside the 20 standard ones."""
    text = "".join(str(sequence).split()).upper()
    if not text:
        raise StepError(f"{operator}: empty protein sequence")
    bad = sorted({aa for aa in text if aa not in _INDEX})
    if bad:
        raise StepError(f"{operator}: unsupported residue(s): {''.join(bad)}")
    return text


def composition(sequence: str) -> list[int]:
    counts = [0] * len(AA20)
    for aa in sequence:
        counts[_INDEX[aa]] += 1
    return counts


def molecular_weight(sequence: str) -> float:
    return sum(_MASS[aa] for aa in sequence) - _WATER * (len(sequence) - 1)


def extinction_coefficients(sequence: str) -> tuple[int, int, float]:
    """Return (molar reduced, molar with cystines, A280 of a 1 mg/ml solution)."""
    reduced = 5500 * sequence.count("W") + 1490 * sequence.count("Y")
    cystine = reduced + 125 * (sequence.count("C") // 2)
    weight = molecular_weight(sequence)
    return reduced, cystine, cystine / weight if weight else float("nan")


def instability_index(sequence: str) -> float:
    score = 0.0
    for first, second in zip(sequence, sequence[1:]):
        score += DIWV[_INDEX[first]][_INDEX[second]]
    return (10.0 / len(sequence)) * score


def raw_sequences(form, sequence_dim: str):
    """Return the reader's original sequences when present and aligned."""
    values = form.info.get("sequences")
    labels = form.labels.get(sequence_dim)
    if isinstance(values, list) and labels is not None and len(values) == len(labels):
        return [str(value).upper() for value in values]
    return None


def prepare_sequences(form, sequence_dim: str, position_dim: str, operator: str):
    """Decode sequences, skipping (and counting) non-standard residue entries."""
    from ._sequence_common import decode_sequences

    decoded = raw_sequences(form, sequence_dim)
    if decoded is None:
        decoded = decode_sequences(form, sequence_dim, position_dim)
    names = list(form.labels[sequence_dim])
    kept_names: list[str] = []
    kept: list[str] = []
    skipped = 0
    for name, sequence in zip(names, decoded):
        try:
            kept.append(clean_sequence(sequence, operator))
        except StepError:
            skipped += 1
            continue
        kept_names.append(name)
    if not kept:
        raise StepError(f"{operator}: no protein sequences with standard residues")
    return kept_names, kept, skipped
