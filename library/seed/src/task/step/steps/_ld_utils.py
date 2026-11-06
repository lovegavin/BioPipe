# src/task/step/steps/_ld_utils.py
"""Shared helpers for linkage-disequilibrium operators.

Genotypes are dosages in [0, 2] read through the VCF reader; missing calls
are NaN.  Operators use complete-case variants (all samples called) and
report how many variants were dropped, so r^2 values are directly
comparable with plink2 ``--r2-unphased`` on the same complete marker set.
"""
from __future__ import annotations

import numpy as np

from src.core import StepError


def genotype_matrix(form, variant_dim, sample_dim, operator):
    dims = list(form.dims)
    if len(dims) != 2:
        raise StepError(f"{operator}: requires a 2D [variant, sample] genotype matrix")
    if dims[0] != variant_dim or dims[1] != sample_dim:
        raise StepError(
            f"{operator}: expected dims [{variant_dim!r}, {sample_dim!r}], got {dims!r}"
        )
    data = np.asarray(form.data, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] < 2 or data.shape[1] < 2:
        raise StepError(f"{operator}: requires at least two variants and two samples")
    called = np.isfinite(data)
    if np.any(data[called] < 0.0) or np.any(data[called] > 2.0):
        raise StepError(f"{operator}: genotype dosages must lie within [0, 2]")
    return data


def variant_positions(form, n_variants, operator):
    pos = form.info.get("pos")
    if not isinstance(pos, (list, tuple)) or len(pos) != n_variants:
        raise StepError(
            f"{operator}: genotype matrix needs one position per variant in info['pos']"
        )
    out = np.asarray([int(p) for p in pos], dtype=np.int64)
    if np.any(out <= 0):
        raise StepError(f"{operator}: variant positions must be positive")
    return out


def allele_frequencies(genotypes):
    called = np.isfinite(genotypes)
    counts = called.sum(axis=1)
    totals = np.where(counts > 0, np.nansum(genotypes, axis=1), 0.0)
    return np.where(counts > 0, totals / (2.0 * np.maximum(counts, 1)), 0.0)


def minor_allele_frequencies(genotypes):
    freq = allele_frequencies(genotypes)
    return np.minimum(freq, 1.0 - freq)


def complete_variant_mask(genotypes):
    return np.isfinite(genotypes).all(axis=1)


def select_variants(n_variants, max_variants):
    """Deterministic, position-preserving subsample (stride over the axis)."""
    if max_variants <= 0 or max_variants >= n_variants:
        return np.arange(n_variants)
    return np.unique(
        np.round(np.linspace(0, n_variants - 1, int(max_variants))).astype(np.int64)
    )


def standardize(genotypes, operator):
    mean = genotypes.mean(axis=1)
    sd = genotypes.std(axis=1)
    mono = sd <= 0.0
    if np.any(mono):
        raise StepError(
            f"{operator}: {int(np.count_nonzero(mono))} variant(s) are monomorphic "
            "and cannot be standardised; raise min_maf or filter them upstream"
        )
    return (genotypes - mean[:, None]) / sd[:, None]


def r2_matrix(z):
    r = (z @ z.T) / z.shape[1]
    return np.clip(r * r, 0.0, 1.0)


def decay_table(positions, z, max_distance, n_bins):
    distances = []
    values = []
    for i in range(z.shape[0] - 1):
        hi = int(np.searchsorted(positions, positions[i] + max_distance, side="right"))
        if hi <= i + 1:
            continue
        r = (z[i + 1:hi] @ z[i]) / z.shape[1]
        distances.append(positions[i + 1:hi] - positions[i])
        values.append(r * r)
    edges = np.linspace(0.0, float(max_distance), int(n_bins) + 1)
    rows = []
    if distances:
        d = np.concatenate(distances)
        v = np.clip(np.concatenate(values), 0.0, 1.0)
    else:
        d = np.zeros(0, dtype=np.int64)
        v = np.zeros(0)
    bins = np.clip(np.digitize(d, edges[1:-1], right=False), 0, int(n_bins) - 1)
    for b in range(int(n_bins)):
        mask = bins == b
        count = int(mask.sum())
        rows.append([
            edges[b],
            edges[b + 1],
            float(count),
            float(v[mask].mean()) if count else 0.0,
            float(np.median(v[mask])) if count else 0.0,
        ])
    return np.asarray(rows, dtype=np.float64)


def prune_variants(genotypes, positions, r2_threshold, window_bp, operator):
    z = standardize(genotypes, operator)
    order = np.argsort(positions, kind="stable")
    kept = []
    for raw in order:
        idx = int(raw)
        if kept:
            kept_arr = np.asarray(kept, dtype=np.int64)
            near = kept_arr[np.abs(positions[kept_arr] - positions[idx]) <= window_bp]
            if near.size:
                r = (z[near] @ z[idx]) / z.shape[1]
                if float(np.max(r * r)) > float(r2_threshold):
                    continue
        kept.append(idx)
    return np.asarray(sorted(kept), dtype=np.int64)
