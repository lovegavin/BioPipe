# src/task/step/steps/normalize.py
"""Normalize a Form along one dimension.

Applies a sample-level normalization. Standard second step after
filtering, for any count-based matrix (RNA-seq, single-cell,
metagenomics, proteomics).

Supported methods
-----------------
    cpm                counts per million: divide each sample by its
                       total, then scale to ``target_sum``
    total              divide each sample by its total (sum = 1)
    median_of_ratios   DESeq2 size factors: per-gene geometric mean,
                       per-sample median of ratios

Layout
------
Input is any Form. The normalization runs along ``dim`` (typically
the sample axis); every other axis is flattened.

Output has the same dims, labels, info and axis_info as the input.
Only ``data`` is replaced.

Params:
    method     : "cpm" | "total" | "median_of_ratios"
    dim        : sample dimension
    target_sum : target total for ``cpm`` (default 1e6)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_METHODS = ("cpm", "total", "median_of_ratios")


class NormalizeStep(Step):
    """Normalize a Form along one dimension."""

    name = "normalize"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        method = ctx.step_params["method"]
        dim = ctx.step_params["dim"]
        target_sum = float(ctx.step_params.get("target_sum", 1e6))
        out_name = ctx.step_params.get("output", self.name)

        if method not in _METHODS:
            raise StepError(
                f"normalize: method must be one of {_METHODS}, "
                f"got {method!r}"
            )
        if dim not in form.dims:
            raise StepError(
                f"normalize: dim '{dim}' is not present. "
                f"Available: {form.dims}"
            )
        if method == "cpm" and target_sum <= 0:
            raise StepError(
                f"normalize: target_sum must be > 0, got {target_sum}"
            )

        axis = form.dims.index(dim)
        moved = np.moveaxis(form.data, axis, 0).astype(np.float64)
        n_samples = moved.shape[0]
        flat = moved.reshape(n_samples, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            valid = ~np.isnan(flat)
        else:
            valid = flat != missing_code

        if method == "cpm":
            size_factors = _cpm(flat, valid, target_sum)
        elif method == "total":
            size_factors = _total(flat, valid)
        else:
            size_factors = _median_of_ratios(flat, valid)

        with np.errstate(invalid="ignore", divide="ignore"):
            normalized = np.where(
                valid,
                flat / size_factors[:, None],
                np.nan,
            )

        # sum_after must be computed in the flat layout, where axis 0
        # is still the sample axis.
        masked_norm = np.where(valid, normalized, 0.0)
        sum_after = masked_norm.sum(axis=1)

        masked = np.where(valid, flat, 0.0)
        sum_before = masked.sum(axis=1)

        normalized = normalized.reshape(moved.shape)
        normalized = np.moveaxis(normalized, 0, axis).astype(np.float32)

        ctx[out_name] = Form(
            data=normalized,
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=dict(form.info),
            axis_info={k: list(v) for k, v in form.axis_info.items()},
        )

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        size_factor_by_label = {
            pos_to_label[i]: float(size_factors[i])
            for i in range(n_samples)
        }

        self._export_data = {
            "method": method,
            "dim": dim,
            "target_sum": target_sum if method == "cpm" else None,
            "n_samples": int(n_samples),
            "size_factors": size_factor_by_label,
            "sum_before": {
                pos_to_label[i]: float(sum_before[i])
                for i in range(n_samples)
            },
            "sum_after": {
                pos_to_label[i]: float(sum_after[i])
                for i in range(n_samples)
            },
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "dim": dim,
            "target_sum": target_sum if method == "cpm" else None,
            "n_samples": int(n_samples),
            "min_size_factor": float(size_factors.min()),
            "max_size_factor": float(size_factors.max()),
        }

        print(
            f"[normalize] method='{method}' dim='{dim}' "
            f"n_samples={n_samples} "
            f"size factors [{size_factors.min():.4g}, "
            f"{size_factors.max():.4g}]"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _cpm(flat, valid, target_sum):
    masked = np.where(valid, flat, 0.0)
    totals = masked.sum(axis=1)
    bad = np.where(totals <= 0)[0]
    if bad.size:
        raise StepError(
            f"normalize/cpm: {bad.size} sample(s) have zero total "
            f"count and cannot be normalized (positions {bad.tolist()[:5]})."
        )
    return totals / target_sum


def _total(flat, valid):
    masked = np.where(valid, flat, 0.0)
    totals = masked.sum(axis=1)
    bad = np.where(totals <= 0)[0]
    if bad.size:
        raise StepError(
            f"normalize/total: {bad.size} sample(s) have zero total "
            f"count and cannot be normalized (positions {bad.tolist()[:5]})."
        )
    return totals


def _median_of_ratios(flat, valid):
    """DESeq2-style size factors.

    For each gene, compute the geometric mean of its valid positive
    counts. A gene is eligible only if all of its valid counts are
    strictly positive (no zero among valid entries). For each
    sample, the size factor is the median over eligible genes of
    (count / geometric mean).
    """
    positive = valid & (flat > 0)
    valid_zero = valid & (flat == 0)
    has_any_valid = valid.any(axis=0)
    has_valid_zero = valid_zero.any(axis=0)
    eligible = has_any_valid & ~has_valid_zero

    if not eligible.any():
        raise StepError(
            "normalize/median_of_ratios: no gene has all-positive "
            "counts; cannot compute size factors."
        )

    eligible_flat = flat[:, eligible]
    eligible_valid = valid[:, eligible]
    masked = np.where(eligible_valid, eligible_flat, np.nan)

    with np.errstate(invalid="ignore", divide="ignore"):
        log_vals = np.log(masked)
        log_mean = np.nanmean(log_vals, axis=0)
        geo_means = np.exp(log_mean)

    if not np.all(np.isfinite(geo_means)):
        raise StepError(
            "normalize/median_of_ratios: geometric means are not "
            "finite for some eligible genes."
        )

    with np.errstate(invalid="ignore", divide="ignore"):
        ratios = masked / geo_means

    with np.errstate(invalid="ignore"):
        size_factors = np.nanmedian(ratios, axis=1)

    bad = ~np.isfinite(size_factors) | (size_factors <= 0)
    if bad.any():
        raise StepError(
            f"normalize/median_of_ratios: {bad.sum()} sample(s) have "
            f"invalid size factors (positions "
            f"{np.where(bad)[0].tolist()[:5]})."
        )

    return size_factors