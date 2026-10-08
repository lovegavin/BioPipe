# src/core/forms/result.py
"""ResultTable — analysis result form.

A unified container for association results, differential expression
outputs, prediction scores, and similar row-indexed analyses. Downstream
writers and report generators consume this form without knowing which
pipeline produced it.

Design principles
-----------------
* The row index is always an ID (variant, gene, interval, sample, feature).
* The ``id_column`` field records the column name once materialized to disk.
* ``id_kind`` records the semantic meaning of the row identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from src.core.errors import ValidationError

# Supported semantics for the row identifier.
ID_KINDS = ("variant", "gene", "interval", "sample", "feature")


@dataclass
class ResultTable:
    """Tabular analysis result indexed by row ID.

    Parameters
    ----------
    data : pd.DataFrame
        Row index is the identifier. Columns are analysis-specific
        (BETA, SE, P, Q_VALUE, ...).
    id_column : str, optional
        Name of the ID column to use when writing to disk.
    id_kind : str, optional
        Semantic kind of the row identifier. One of :data:`ID_KINDS`.
    source_format : str, optional
        Origin of this form. Defaults to ``"derived"``.
    """

    data: pd.DataFrame
    id_column: str = "ID"
    id_kind: str = "variant"
    source_format: str = "derived"

    # ------------------------------------------------------------------ #
    # Properties
    # ------------------------------------------------------------------ #

    @property
    def n_rows(self) -> int:
        """Number of result rows."""
        return int(self.data.shape[0])

    @property
    def n_cols(self) -> int:
        """Number of result columns."""
        return int(self.data.shape[1])

    @property
    def row_ids(self):
        """Row identifiers as a pandas Index."""
        return self.data.index

    # ------------------------------------------------------------------ #
    # Subsetting
    # ------------------------------------------------------------------ #

    def subset_rows(self, mask) -> "ResultTable":
        """Return a new result restricted to rows selected by ``mask``.

        Parameters
        ----------
        mask : sequence of bool or int
            Boolean mask over rows, or positional row indices.
        """
        if hasattr(mask, "dtype") and getattr(mask, "dtype") == bool:
            new_data = self.data.loc[mask]
        else:
            new_data = self.data.iloc[mask]

        return ResultTable(
            data=new_data.copy(),
            id_column=self.id_column,
            id_kind=self.id_kind,
            source_format=self.source_format,
        )

    def subset_cols(self, cols) -> "ResultTable":
        """Return a new result restricted to ``cols``."""
        new_data = self.data.loc[:, list(cols)]
        return ResultTable(
            data=new_data.copy(),
            id_column=self.id_column,
            id_kind=self.id_kind,
            source_format=self.source_format,
        )

    # ------------------------------------------------------------------ #
    # Validation
    # ------------------------------------------------------------------ #

    def validate(self) -> None:
        """Enforce structural invariants. Raises :class:`ValidationError`."""
        if not isinstance(self.data, pd.DataFrame):
            raise ValidationError(
                "ResultTable", "data must be a pandas DataFrame"
            )

        if not self.data.index.is_unique:
            raise ValidationError(
                "ResultTable", "row index contains duplicates"
            )

        if self.id_kind not in ID_KINDS:
            raise ValidationError(
                "ResultTable",
                "unsupported id_kind",
                f"id_kind={self.id_kind} allowed={ID_KINDS}",
            )