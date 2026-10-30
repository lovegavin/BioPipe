# src/task/step/steps/normalize.py
"""Normalize a Form along one dimension.

Applies a sample-level normalization. Standard second step after
filtering, for any count or intensity matrix (RNA-seq, proteomics,
metabolomics, single-cell).

Supported methods
-----------------
    cpm                counts per million: divide each sample by its
                       total, then scale to ``target_sum``
    total              divide each sample by its total (sum = 1)
    median_of_ratios   DESeq2 size factors: per-gene geometric mean,
                       per-sample median of ratios
    quantile           quantile normalization: for each rank position,
                       replace the value with the mean of that rank
                       across all samples
    zscore             z-score each sample (mean 0, std 1)

Layout
------
Input is any Form. The normalization runs along ``dim`` (typically
the sample axis); every other axis is flattened.

Output has the same dims, labels, info and axis_info as the input.
Only ``data`` is replaced.

Params:
    method     : "cpm" | "total" | "median_of_ratios" | "quantile"
                 | "zscore"
    dim        : sample dimension
    target_sum : target total for ``cpm`` (default 1e6)
    output     : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.core.forms.metadata import project_metadata


_METHODS = (
    "cpm", "total", "median_of_ratios", "quantile", "zscore",
)
_SIZE_FACTOR_METHODS = ("cpm", "total", "median_of_ratios")


class NormalizeStep(Step):
    """Normalize a Form along one dimension."""
    provider = 'biopipe-expression'
    parameters_file = 'normalize.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'normalize',
     'version': '1.0.0',
     'kind': 'operator',
     'title': '归一化',
     'description': 'CPM、DESeq2 size factors、Quantile 或 Z-score',
     'category': '数据整理',
     'icon': 'SlidersHorizontal',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [],
                               'parallel': []}],
                   'output': {'mode': 'transform', 'representation': 'normalize'}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        method = ctx.step_params.get("method")
        dim = ctx.step_params.get("dim")
        target_sum = float(ctx.step_params.get("target_sum", 1e6))
        out_name = ctx.step_params.get("output", self.name)

        if method not in _METHODS:
            raise StepError(
                f"normalize: method must be one of {_METHODS}, "
                f"got {method!r}"
            )
        if dim is None:
            raise StepError("normalize: 'dim' is required")
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

        size_factors = None
        if method == "cpm":
            size_factors = _cpm(flat, valid, target_sum)
        elif method == "total":
            size_factors = _total(flat, valid)
        elif method == "median_of_ratios":
            size_factors = _median_of_ratios(flat, valid)

        if method in _SIZE_FACTOR_METHODS:
            with np.errstate(invalid="ignore", divide="ignore"):
                normalized = np.where(
                    valid, flat / size_factors[:, None], np.nan,
                )
        elif method == "quantile":
            normalized = _quantile(flat, valid)
        else:  # zscore
            normalized = _zscore(flat, valid)

        pos_to_label = {v: k for k, v in form.labels[dim].items()}
        masked_before = np.where(valid, flat, np.nan)
        masked_after = np.where(valid, normalized, np.nan)

        per_sample = {}
        for i in range(n_samples):
            label = pos_to_label[i]
            before_row = masked_before[i]
            after_row = masked_after[i]
            finite_before = before_row[np.isfinite(before_row)]
            finite_after = after_row[np.isfinite(after_row)]

            entry = {
                "sum_before": float(np.nansum(before_row)),
                "sum_after": float(np.nansum(after_row)),
                "min_before": (
                    float(finite_before.min())
                    if finite_before.size else None
                ),
                "min_after": (
                    float(finite_after.min())
                    if finite_after.size else None
                ),
                "max_before": (
                    float(finite_before.max())
                    if finite_before.size else None
                ),
                "max_after": (
                    float(finite_after.max())
                    if finite_after.size else None
                ),
                "mean_before": (
                    float(finite_before.mean())
                    if finite_before.size else None
                ),
                "mean_after": (
                    float(finite_after.mean())
                    if finite_after.size else None
                ),
                "std_before": (
                    float(finite_before.std())
                    if finite_before.size else None
                ),
                "std_after": (
                    float(finite_after.std())
                    if finite_after.size else None
                ),
            }
            if size_factors is not None:
                entry["size_factor"] = float(size_factors[i])
            per_sample[label] = entry

        normalized = normalized.reshape(moved.shape)
        normalized = np.moveaxis(normalized, 0, axis).astype(np.float32)

        info, axis_info = project_metadata(form, derived=True)
        info.update(missing_code=np.nan, representation="normalize")
        ctx[out_name] = Form(
            data=normalized,
            dims=list(form.dims),
            labels={k: dict(v) for k, v in form.labels.items()},
            info=info,
            axis_info=axis_info,
        )

        self._export_data = {
            "method": method,
            "dim": dim,
            "target_sum": target_sum if method == "cpm" else None,
            "n_samples": int(n_samples),
            "per_sample": per_sample,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "method": method,
            "dim": dim,
            "n_samples": int(n_samples),
        }

        if size_factors is not None:
            print(
                f"[normalize] method='{method}' dim='{dim}' "
                f"n_samples={n_samples} "
                f"size factors [{size_factors.min():.4g}, "
                f"{size_factors.max():.4g}]"
            )
        else:
            print(
                f"[normalize] method='{method}' dim='{dim}' "
                f"n_samples={n_samples}"
            )

    def export(self, ctx: Context) -> dict:
        return self._export_data


# ------------------------------------------------------------------ #
# Size-factor methods
# ------------------------------------------------------------------ #

def _cpm(flat, valid, target_sum):
    masked = np.where(valid, flat, 0.0)
    totals = masked.sum(axis=1)
    bad = np.where(totals <= 0)[0]
    if bad.size:
        raise StepError(
            f"normalize/cpm: {bad.size} sample(s) have zero total "
            f"count and cannot be normalized "
            f"(positions {bad.tolist()[:5]})."
        )
    return totals / target_sum


def _total(flat, valid):
    masked = np.where(valid, flat, 0.0)
    totals = masked.sum(axis=1)
    bad = np.where(totals <= 0)[0]
    if bad.size:
        raise StepError(
            f"normalize/total: {bad.size} sample(s) have zero total "
            f"count and cannot be normalized "
            f"(positions {bad.tolist()[:5]})."
        )
    return totals


def _median_of_ratios(flat, valid):
    """DESeq2-style size factors.

    For each gene, compute the geometric mean of its valid positive
    counts. A gene is eligible only if all of its valid counts are
    strictly positive. For each sample, the size factor is the median
    over eligible genes of (count / geometric mean).
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


# ------------------------------------------------------------------ #
# Quantile normalization
# ------------------------------------------------------------------ #

def _quantile(flat, valid):
    """Quantile normalization.

    Rows of ``flat`` are samples, columns are features. For each rank
    position k (0-indexed), the target value is the mean of the k-th
    smallest valid value across all samples. Each sample's sorted
    values are then replaced by these target values.

    When samples have different numbers of valid values, the ranking
    depth is the minimum valid count across samples. The remaining
    values in a sample keep the last target value.
    """
    n_samples, n_features = flat.shape
    result = np.full_like(flat, np.nan, dtype=np.float64)

    n_valid = valid.sum(axis=1)
    if n_valid.min() == 0:
        raise StepError(
            "normalize/quantile: a sample has no valid values."
        )

    n_q = int(n_valid.min())

    sorted_trimmed = np.full((n_samples, n_q), np.nan, dtype=np.float64)
    for i in range(n_samples):
        vals = flat[i][valid[i]]
        sorted_trimmed[i] = np.sort(vals)[:n_q]

    target = sorted_trimmed.mean(axis=0)

    for i in range(n_samples):
        vals = flat[i]
        vmask = valid[i]
        n = int(vmask.sum())
        order = np.argsort(vals[vmask])
        if n <= n_q:
            new_vals = target[:n]
        else:
            tail = np.full(n - n_q, target[-1])
            new_vals = np.concatenate([target, tail])
        filled = np.empty(n, dtype=np.float64)
        filled[order] = new_vals
        result[i, vmask] = filled

    return result


# ------------------------------------------------------------------ #
# Z-score
# ------------------------------------------------------------------ #

def _zscore(flat, valid):
    masked = np.where(valid, flat, np.nan)
    with np.errstate(invalid="ignore"):
        mu = np.nanmean(masked, axis=1, keepdims=True)
        sd = np.nanstd(masked, axis=1, keepdims=True)
    sd = np.where(sd > 1e-12, sd, 1.0)
    with np.errstate(invalid="ignore", divide="ignore"):
        normalized = (flat - mu) / sd
    return np.where(valid, normalized, np.nan)