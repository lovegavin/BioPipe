"""Shared helpers for position weight matrix operators."""
from __future__ import annotations

import numpy as np

from src.core import StepError

BASES = ("A", "C", "G", "T")
_COMPLEMENT = {"A": "T", "C": "G", "G": "C", "T": "A", "N": "N"}


def reverse_complement(sequence: str) -> str:
    return "".join(_COMPLEMENT.get(base, "N") for base in reversed(sequence.upper()))


def parse_background(text: str) -> np.ndarray:
    parts = [part.strip() for part in str(text).split(",") if part.strip()]
    if len(parts) != 4:
        raise StepError("pwm: background must list four frequencies A,C,G,T")
    values = np.array([float(part) for part in parts], dtype=np.float64)
    if np.any(values <= 0) or not np.isfinite(values).all():
        raise StepError("pwm: background frequencies must be positive and finite")
    return values / values.sum()


def counts_matrix(form, position_dim: str, base_dim: str) -> np.ndarray:
    if len(form.dims) != 2:
        raise StepError("pwm: counts table must be two-dimensional")
    if position_dim not in form.labels or base_dim not in form.labels:
        raise StepError(f"pwm: table must declare {position_dim!r} and {base_dim!r} dimensions")
    base_labels = form.labels[base_dim]
    missing = [base for base in BASES if base not in base_labels]
    if missing:
        raise StepError(f"pwm: counts table is missing base column(s): {', '.join(missing)}")
    data = np.asarray(form.data, dtype=np.float64)
    if data.ndim != 2:
        raise StepError("pwm: counts table must be a matrix")
    order = [base_labels[base] for base in BASES]
    matrix = data[:, order]
    if np.any(matrix < 0) or not np.isfinite(matrix).all():
        raise StepError("pwm: counts must be finite and non-negative")
    if np.any(matrix.sum(axis=1) <= 0):
        raise StepError("pwm: every position needs a positive total count")
    return matrix


def pwm_matrix(counts: np.ndarray, pseudocount: float, background: np.ndarray):
    total = counts.sum(axis=1, keepdims=True)
    probabilities = (counts + pseudocount) / (total + 4.0 * pseudocount)
    pwm = np.log2(probabilities / background[None, :])
    return pwm, probabilities


def information_content(probabilities: np.ndarray, background: np.ndarray) -> np.ndarray:
    return (probabilities * np.log2(probabilities / background[None, :])).sum(axis=1)


def read_pwm(form, position_dim: str, base_dim: str) -> np.ndarray:
    """Read a log-odds PWM table (values may be negative)."""
    if len(form.dims) != 2:
        raise StepError("pwm: PWM table must be two-dimensional")
    if position_dim not in form.labels or base_dim not in form.labels:
        raise StepError(f"pwm: table must declare {position_dim!r} and {base_dim!r} dimensions")
    base_labels = form.labels[base_dim]
    missing = [base for base in BASES if base not in base_labels]
    if missing:
        raise StepError(f"pwm: PWM table is missing base column(s): {', '.join(missing)}")
    data = np.asarray(form.data, dtype=np.float64)
    if data.ndim != 2:
        raise StepError("pwm: PWM table must be a matrix")
    order = [base_labels[base] for base in BASES]
    matrix = data[:, order]
    if not np.isfinite(matrix).all():
        raise StepError("pwm: PWM scores must be finite")
    return matrix


def best_base(probabilities: np.ndarray) -> str:
    return "".join(BASES[index] for index in np.argmax(probabilities, axis=1))


def scan_pwm(pwm: np.ndarray, sequence: str, min_score: float, both_strands: bool):
    """Return hits as (position, strand, score, site) with forward-strand coordinates."""
    width = pwm.shape[0]
    seq = str(sequence).upper()
    hits = []
    if len(seq) < width:
        return hits
    strands = [("+", seq)]
    if both_strands:
        strands.append(("-", reverse_complement(seq)))
    index = np.arange(width)
    for strand, text in strands:
        for start in range(0, len(text) - width + 1):
            site = text[start:start + width]
            try:
                codes = [BASES.index(base) for base in site]
            except ValueError:
                continue
            score = float(pwm[index, codes].sum())
            if score < min_score:
                continue
            if strand == "+":
                position = start
            else:
                position = len(seq) - start - width
            hits.append((position, strand, score, seq[position:position + width]))
    hits.sort(key=lambda item: (-item[2], item[0], item[1]))
    return hits
