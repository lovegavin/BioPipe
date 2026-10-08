# src/core/forms/protocol.py
"""Structural protocols shared across memory forms.

A form implements :class:`SampleIndexed` when it exposes a sample
dimension keyed by sample ID. Any such form can participate in
:func:`src.align.align_forms` without the aligner knowing which form
type it is.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import numpy as np


@runtime_checkable
class SampleIndexed(Protocol):
    """A form with a sample dimension indexed by sample ID.

    Implementations must provide:

    * ``sample_ids`` — a sequence of unique sample identifiers.
    * ``subset_samples(ids)`` — return a new form restricted to (and
      reordered by) ``ids``. The returned object must preserve the
      same form type.
    """

    @property
    def sample_ids(self) -> np.ndarray:
        ...

    def subset_samples(self, ids) -> "SampleIndexed":
        ...