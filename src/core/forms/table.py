# src/core/forms/table.py
"""Table — generic two-dimensional tabular form.

Used for phenotype tables, covariate tables and any tabular input whose
rows share a single identifier. By convention the row identifier is a
sample ID, which lets the table participate in sample alignment.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.core.errors import ValidationError


@dataclass
class Table:
    """Generic tabular data indexed by row ID.

    Parameters
    ----------
    data : pd.DataFrame
        Index is the row identifier (sample ID by convention).
    index_name : str
        Name of the index column (informational only).
    source_format : str
        Reader that produced this form.
    """

    data: pd.DataFrame
    index_name: str = "id"
    source_format: str = "unknown"

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def index(self):
        return self.data.index

    @property
    def columns(self):
        return self.data.columns

    @property
    def shape(self) -> tuple[int, int]:
        return self.data.shape

    @property
    def sample_ids(self) -> np.ndarray:
        """Row identifiers exposed as a numpy array.

        Satisfies the :class:`SampleIndexed` protocol. For phenotype
        and covariate tables the row identifiers are sample IDs.
        """
        return self.data.index.to_numpy()

    # ------------------------------------------------------------------ #
    # Sample-indexed protocol
    # ------------------------------------------------------------------ #

    def subset_samples(self, ids) -> "Table":
        """Return a new table restricted to (and reordered by) row IDs.

        Alias for :meth:`subset_rows`. Provided so that ``Table``
        satisfies :class:`SampleIndexed` and can participate in
        form-agnostic alignment.
        """
        return self.subset_rows(ids)

    def subset_rows(self, ids) -> "Table":
        """Return a new table restricted to (and reordered by) ``ids``."""
        ids = [str(s) for s in ids]
        missing = [s for s in ids if s not in self.data.index]
        if missing:
            preview = ", ".join(missing[:5])
            more = "" if len(missing) <= 5 else f" (+{len(missing) - 5} more)"
            raise KeyError(
                f"Table.subset_rows: unknown row IDs: {preview}{more}"
            )
        new_data = self.data.loc[ids]
        return Table(
            data=new_data.copy(),
            index_name=self.index_name,
            source_format=self.source_format,
        )

    def subset_cols(self, cols) -> "Table":
        """Return a new table restricted to ``cols``."""
        new_data = self.data.loc[:, list(cols)]
        return Table(
            data=new_data.copy(),
            index_name=self.index_name,
            source_format=self.source_format,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        if not isinstance(self.data, pd.DataFrame):
            raise ValidationError(
                "Table", "data must be a pandas DataFrame"
            )
        if not self.data.index.is_unique:
            raise ValidationError("Table", "index contains duplicates")