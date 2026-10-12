# src/reader/readers/_encoder.py
"""Shared label encoders for tabular readers.

Each encoder exposes:

    name             — short identifier ("labelencoder", ...)
    fit_transform(x) — fit on x, return float32 codes
    inverse_transform(codes) — map codes back to original values
    mapping          — {original: code}
    inverse          — {code: original}
"""

from __future__ import annotations

import numpy as np

from src.core import ReaderError


class LabelEncoder:
    """Map each unique value to an integer in first-appearance order."""

    name = "labelencoder"

    def __init__(self) -> None:
        self.mapping: dict = {}
        self.inverse: dict = {}

    def fit_transform(self, values) -> np.ndarray:
        order = list(dict.fromkeys(values))
        self.mapping = {v: i for i, v in enumerate(order)}
        self.inverse = {i: v for v, i in self.mapping.items()}
        return np.asarray(
            [self.mapping[v] for v in values], dtype=np.float32
        )

    def inverse_transform(self, codes) -> list:
        return [self.inverse[int(c)] for c in codes]


_ENCODERS = {
    "labelencoder": LabelEncoder,
}


def get_encoder(name: str):
    if name not in _ENCODERS:
        raise ReaderError(
            f"Unknown encoder '{name}'. "
            f"Available: {sorted(_ENCODERS)}"
        )
    return _ENCODERS[name]()