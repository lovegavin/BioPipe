# src/core/forms/sample.py
"""SampleTable — sample-level metadata."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.core.errors import ValidationError


@dataclass
class SampleTable:
    """Sample metadata indexed by sample ID.

    Parameters
    ----------
    data : pd.DataFrame
        Index is the sample ID (string). Columns are arbitrary metadata.
    source_format : str
        Reader that produced this form.
    """

    data: pd.DataFrame
    source_format: str = "unknown"

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def sample_ids(self) -> np.ndarray:
        return self.data.index.to_numpy()

    @property
    def n_samples(self) -> int:
        return int(self.data.shape[0])

    # ------------------------------------------------------------------ #
    # Sample-indexed protocol
    # ------------------------------------------------------------------ #

    def subset_samples(self, ids) -> "SampleTable":
        """Return a new table restricted to (and reordered by) ``ids``."""
        ids = [str(s) for s in ids]
        missing = [s for s in ids if s not in self.data.index]
        if missing:
            preview = ", ".join(missing[:5])
            more = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise KeyError(
                f"SampleTable.subset_samples: unknown sample IDs: "
                f"{preview}{more}"
            )
        new_data = self.data.loc[ids]
        return SampleTable(
            data=new_data.copy(),
            source_format=self.source_format,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if not isinstance(self.data, pd.DataFrame):
            raise ValidationError(
                "SampleTable", "data must be a pandas DataFrame"
            )
        if not self.data.index.is_unique:
            raise ValidationError(
                "SampleTable", "sample index contains duplicates"
            )