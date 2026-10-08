# src/core/forms/variant.py
"""VariantTable — variant-level metadata."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.core.errors import ValidationError

REQUIRED_COLUMNS = ("CHROM", "POS", "REF", "ALT")


@dataclass
class VariantTable:
    """Variant metadata indexed by variant ID.

    Parameters
    ----------
    data : pd.DataFrame
        Index is the variant ID (string). Must contain columns:
        ``CHROM``, ``POS``, ``REF``, ``ALT``.
    genome_build : str
        Reference build label.
    source_format : str
        Reader that produced this form.
    """

    data: pd.DataFrame
    genome_build: str = "unknown"
    source_format: str = "unknown"

    @property
    def variant_ids(self) -> np.ndarray:
        return self.data.index.to_numpy()

    @property
    def n_variants(self) -> int:
        return int(self.data.shape[0])

    def subset(self, mask) -> "VariantTable":
        """Return a new table restricted to variants selected by ``mask``."""
        mask = np.asarray(mask)
        if mask.dtype == bool:
            new_data = self.data.loc[mask]
        else:
            new_data = self.data.iloc[mask]
        return VariantTable(
            data=new_data.copy(),
            genome_build=self.genome_build,
            source_format=self.source_format,
        )

    def validate(self) -> None:
        if not isinstance(self.data, pd.DataFrame):
            raise ValidationError(
                "VariantTable", "data must be a pandas DataFrame"
            )

        missing = [c for c in REQUIRED_COLUMNS if c not in self.data.columns]
        if missing:
            raise ValidationError(
                "VariantTable",
                "missing required columns",
                f"missing={missing}",
            )

        if not self.data.index.is_unique:
            raise ValidationError(
                "VariantTable", "variant index contains duplicates"
            )