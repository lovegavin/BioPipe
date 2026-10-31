"""Lossless numeric compaction shared by readers and genomic operators.

``float32`` cannot represent every integer above ``2**24``. Genomic
coordinates routinely exceed that (human chromosomes reach ~2.5e8), so
storing a coordinate column directly as float32 silently changes
positions. Readers parse numeric columns as float64 and narrow the
finished matrix to float32 only when that cast is exact. Operators that
emit coordinates, spans or base-pair totals use the same helper, so a
small table keeps the compact float32 representation while a genomic
coordinate table keeps exact float64 values.
"""
from __future__ import annotations

import numpy as np


def compact_numeric(data: np.ndarray) -> np.ndarray:
    """Return float32 when every value is exactly representable, else float64."""
    array = np.asarray(data, dtype=np.float64)
    if array.size == 0:
        return array.astype(np.float32)
    narrowed = array.astype(np.float32)
    if np.array_equal(array, narrowed, equal_nan=True):
        return narrowed
    return array


__all__ = ["compact_numeric"]
