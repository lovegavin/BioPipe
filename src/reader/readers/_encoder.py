# src/reader/readers/_encoder.py
"""Shared label encoders for tabular readers."""

from __future__ import annotations

import numpy as np

from src.core import ReaderError


class _LabelEncoder:
    """Map each unique value to an integer in first-appearance order."""

    def fit_transform(self, values) -> np.ndarray:
        order = list(dict.fromkeys(values))
        mapping = {v: i for i, v in enumerate(order)}
        return np.asarray([mapping[v] for v in values], dtype=np.float32)


_ENCODERS = {"labelencoder": _LabelEncoder}


def get_encoder(name: str):
    if name not in _ENCODERS:
        raise ReaderError(
            f"Unknown encoder '{name}'. Available: {sorted(_ENCODERS)}"
        )
    return _ENCODERS[name]()