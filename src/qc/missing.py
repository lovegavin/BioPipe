# src/qc/missing.py
"""Missingness statistics and sample-level filtering."""

from __future__ import annotations

import numpy as np

from src.core.forms import GenotypeMatrix, Table


def compute_missing_rate(data: np.ndarray, missing_code: float = -1.0,
                         axis: int = 1) -> np.ndarray:
    """Fraction of missing calls along ``axis``.

    Parameters
    ----------
    data : np.ndarray
        Genotype dosage matrix.
    missing_code : float
        Sentinel value for missing calls.
    axis : int
        0 for per-sample, 1 for per-variant.

    Returns
    -------
    np.ndarray
        Missing rate per row or column.
    """
    mask = data == missing_code
    return mask.mean(axis=axis)


def filter_by_sample_missing(
    genotype: GenotypeMatrix,
    phenotype: Table,
    covariates: Table | None,
    threshold: float,
) -> tuple[GenotypeMatrix, Table, Table | None, dict]:
    """Drop samples whose missing rate exceeds ``threshold``.

    Parameters
    ----------
    threshold : float
        Maximum allowed per-sample missing rate. ``None`` disables
        filtering.

    Returns
    -------
    (genotype, phenotype, covariates, report)
    """
    n_before = genotype.n_samples

    if threshold is None:
        return genotype, phenotype, covariates, {
            "applied": False,
            "n_samples_before": int(n_before),
            "n_samples_after": int(n_before),
            "n_removed": 0,
        }

    rates = compute_missing_rate(
        genotype.data, genotype.missing_code, axis=0
    )
    keep_mask = rates <= threshold
    n_kept = int(keep_mask.sum())

    if n_kept == 0:
        raise ValueError(
            "Sample missingness filter removed every sample. "
            "Relax the threshold or inspect the input."
        )

    if n_kept < n_before:
        genotype = genotype.subset_samples(keep_mask)
        phenotype = phenotype.subset_rows(genotype.sample_ids.tolist())
        if covariates is not None:
            covariates = covariates.subset_rows(
                genotype.sample_ids.tolist()
            )

    report = {
        "applied": True,
        "threshold": float(threshold),
        "n_samples_before": int(n_before),
        "n_samples_after": int(n_kept),
        "n_removed": int(n_before - n_kept),
    }
    print(
        f"[qc] sample missingness: {n_before} -> {n_kept} "
        f"(threshold={threshold})"
    )
    return genotype, phenotype, covariates, report