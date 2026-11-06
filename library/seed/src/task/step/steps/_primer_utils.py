"""Primer thermodynamics and in-silico PCR helpers.

The melting temperature uses the unified nearest-neighbour parameters of
SantaLucia (1998) with the salt correction that adjusts the entropy term,
matching the formulation used by Biopython's ``MeltingTemp.Tm_NN``.
"""

from __future__ import annotations

import math

import numpy as np

from src.core import StepError

_COMPLEMENT = str.maketrans("ACGTNacgtn", "TGCANtgcan")

# Unified NN parameters (SantaLucia 1998), kcal/mol and cal/(mol K).
_NN = {
    "AA": (-7.9, -22.2), "TT": (-7.9, -22.2),
    "AT": (-7.2, -20.4), "TA": (-7.2, -21.3),
    "CA": (-8.5, -22.7), "TG": (-8.5, -22.7),
    "GT": (-8.4, -22.4), "AC": (-8.4, -22.4),
    "CT": (-7.8, -21.0), "AG": (-7.8, -21.0),
    "GA": (-8.2, -22.2), "TC": (-8.2, -22.2),
    "CG": (-10.6, -27.2), "GC": (-9.8, -24.4),
    "GG": (-8.0, -19.9), "CC": (-8.0, -19.9),
}
_INIT_GC = (0.1, -2.8)
_INIT_AT = (2.3, 4.1)
_GAS_CONSTANT = 1.987  # cal/(mol K)


def clean_sequence(sequence: str, operator: str) -> str:
    """Uppercase a nucleotide sequence and reject non-ACGTN characters."""

    text = sequence.strip().upper().replace("U", "T")
    bad = sorted({char for char in text if char not in "ACGTN"})
    if bad:
        raise StepError(f"{operator}: unsupported nucleotide characters {bad}")
    return text


def reverse_complement(sequence: str) -> str:
    return sequence.translate(_COMPLEMENT)[::-1]


def gc_fraction(sequence: str) -> float:
    if not sequence:
        return 0.0
    return (sequence.count("G") + sequence.count("C")) / float(len(sequence))


def tm_nn(
    sequence: str,
    *,
    na_mm: float = 50.0,
    dnac_nm: float = 25.0,
    salt_correction: bool = True,
) -> tuple[float, float, float]:
    """Nearest-neighbour Tm (degC) and the enthalpy/entropy terms."""

    if len(sequence) < 2:
        raise StepError("primer_tm: a sequence needs at least two bases")
    if na_mm <= 0:
        raise StepError("primer_tm: sodium concentration must be positive")
    delta_h = 0.0
    delta_s = 0.0
    for base in (sequence[0], sequence[-1]):
        init_h, init_s = _INIT_GC if base in "GC" else _INIT_AT
        delta_h += init_h
        delta_s += init_s
    for index in range(len(sequence) - 1):
        pair = sequence[index:index + 2]
        if pair not in _NN:
            raise StepError(f"primer_tm: cannot evaluate dinucleotide {pair!r}")
        nn_h, nn_s = _NN[pair]
        delta_h += nn_h
        delta_s += nn_s
    concentration = (dnac_nm - dnac_nm / 2.0) * 1e-9
    if salt_correction:
        delta_s += 0.368 * (len(sequence) - 1) * math.log(na_mm * 1e-3)
    tm = 1000.0 * delta_h / (delta_s + _GAS_CONSTANT * math.log(concentration)) - 273.15
    return tm, delta_h, delta_s


def count_mismatches(primer: str, target: str) -> int:
    return sum(1 for left, right in zip(primer, target) if left != right)


def scan_hits(primer: str, sequence: str, max_mismatches: int) -> list[tuple[int, int]]:
    """Return ``(start, mismatches)`` for every near-match of the primer."""

    hits: list[tuple[int, int]] = []
    size = len(primer)
    if size == 0 or size > len(sequence):
        return hits
    for start in range(len(sequence) - size + 1):
        mismatches = 0
        for offset in range(size):
            if primer[offset] != sequence[start + offset]:
                mismatches += 1
                if mismatches > max_mismatches:
                    break
        else:
            hits.append((start, mismatches))
    return hits


def fit_primer(
    sequence: str,
    *,
    min_length: int,
    max_length: int,
    min_tm: float,
    max_tm: float,
    min_gc: float,
    max_gc: float,
    na_mm: float,
    dnac_nm: float,
    operator: str,
) -> bool:
    size = len(sequence)
    if not (min_length <= size <= max_length):
        return False
    fraction = gc_fraction(sequence)
    if not (min_gc <= fraction * 100.0 <= max_gc):
        return False
    tm, _, _ = tm_nn(sequence, na_mm=na_mm, dnac_nm=dnac_nm)
    return min_tm <= tm <= max_tm


def relative_penalty(value: float, optimum: float, weight: float) -> float:
    return weight * abs(value - optimum)
