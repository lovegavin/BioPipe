# src/qc/maf.py
"""Minor allele frequency computation."""

from __future__ import annotations

import numpy as np


def compute_maf(data: np.ndarray, ploidy: int,
                missing_code: float = -1.0) -> np.ndarray:
    """Return MAF per variant (row).

    Parameters
    ----------
    data : np.ndarray
        Genotype dosage matrix, shape ``(n_snps, n_samples)``.
    ploidy : int
        Allele copies per genotype call.
    missing_code : float

    Returns
    -------
    np.ndarray
        MAF per variant, shape ``(n_snps,)``. Variants with no valid
        calls yield ``NaN``.
    """
    valid = np.where(data == missing_code, np.nan, data)
    alt_freq = np.nanmean(valid, axis=1) / ploidy
    maf = np.minimum(alt_freq, 1.0 - alt_freq)
    return maf