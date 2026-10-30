# src/task/step/steps/correlation.py
"""Pairwise correlation matrix along one axis of a form.

For every pair of positions along ``dim``, computes the correlation
of their values across the other axes. The output is a square form
with the same labels on both axes.

This is the natural companion of ``distance_matrix``. Where
``distance_matrix`` measures dissimilarity, this measures
similarity. Both are useful for sample QC, feature clustering,
co-expression analysis, and as input to a heatmap.

Output dims
-----------
    dims = [dim, f"{dim}_b"]

Both axes carry the same labels, in the same order. ``form.data[i, j]``
is the correlation between position ``i`` and position ``j``.

Metrics
-------
    pearson       Pearson product-moment correlation (default)
    spearman      Spearman rank correlation
    kendall       Kendall's tau
    cosine        cosine similarity (dot product of normalized rows)
    jaccard       Jaccard similarity on binarized (>0) values
    overlap       overlap coefficient |A and B| / min(|A|, |B|),
                  on binarized (>0) values

Missing values
--------------
Missing cells are handled pairwise: for each pair (i, j), only
positions where both i and j are valid contribute to the
correlation. This matches the standard treatment of missing data in
correlation matrices.

Size guard
----------
The output is a dense ``n x n`` matrix. The memory planner accounts for its
quadratic allocation. An optional ``max_positions`` adds a count limit;
the default is None, leaving admission to the configured memory budget.

Params:
    dim            : axis to compute correlations along (required)
    metric         : metric name (default "pearson")
    min_valid      : minimum number of valid positions per pair
                     (default 3)
    max_positions  : refuse if dim has more positions than this
                     (default None; governed by the memory budget)
    output         : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step
from src.task.step.steps._microbiome import estimate, metadata


_METRICS = (
    "pearson", "spearman", "kendall",
    "cosine", "jaccard", "overlap",
)


class CorrelationStep(Step):
    """Pairwise correlation matrix along one axis."""
    provider = 'biopipe-microbiome'
    parameters_file = 'correlation.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'correlation',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Correlation',
     'description': 'Pairwise correlation matrix along one axis.',
     'category': '统计分析',
     'icon': 'Intersect',
     'contracts': {'version': 1,
                   'inputs': [{'version': 1,
                               'numeric': True,
                               'info': {},
                               'dims': [{'param': 'dim', 'default': None}],
                               'labels': [],
                               'parallel': []}],
                   'output': {'mode': 'project',
                              'derived': True,
                              'info': {'missing_code': {'type': ['number', 'null']},
                                       'representation': {'type': 'string', 'const': 'correlation'}},
                              'keep_dims': [{'param': 'dim', 'default': None}],
                              'append_dims': [{'name': {'param': 'dim', 'suffix': '_b'},
                                               'labels_from': {'param': 'dim', 'default': None}}]}},
     'resources': {'memory_modes': ['full'], 'supports_cuda': False, 'estimate': 'estimate_memory'},
     'inputs_arity': 1,
     'outputs': [],
     'output_parameter': 'output'}



    @classmethod
    def estimate_memory(cls, inputs, params, profiles):
        return estimate(cls.name, inputs, params, profiles)

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        metric = ctx.step_params.get("metric", "pearson")
        min_valid = int(ctx.step_params.get("min_valid", 3))
        max_positions = ctx.step_params.get("max_positions")
        if max_positions is not None:
            max_positions = int(max_positions)
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("correlation: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"correlation: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if metric not in _METRICS:
            raise StepError(
                f"correlation: metric must be one of "
                f"{list(_METRICS)}, got {metric!r}"
            )
        if min_valid < 2:
            raise StepError(
                f"correlation: min_valid must be >= 2, "
                f"got {min_valid}"
            )
        if max_positions is not None and max_positions < 1:
            raise StepError(
                f"correlation: max_positions must be >= 1, "
                f"got {max_positions}"
            )

        axis = form.dims.index(dim)
        n_positions = form.data.shape[axis]
        if max_positions is not None and n_positions > max_positions:
            raise StepError(
                f"correlation: dim '{dim}' has {n_positions} "
                f"positions, which would produce a "
                f"{n_positions}x{n_positions} dense matrix. "
                f"Raise 'max_positions' explicitly if you need this."
            )
        if n_positions < 2:
            raise StepError(
                f"correlation: dim '{dim}' has only "
                f"{n_positions} position(s)"
            )

        moved = np.moveaxis(form.data, axis, 0).astype(np.float64)
        flat = moved.reshape(n_positions, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(flat)
        else:
            missing = flat == missing_code
        valid = ~missing

        corr = _compute_correlation(
            metric, flat, valid, min_valid
        )

        # Symmetrize and set diagonal to 1 for bounded metrics.
        corr = 0.5 * (corr + corr.T)
        diag_value = 1.0
        np.fill_diagonal(corr, diag_value)

        out_dim_b = f"{dim}_b"
        out_labels = {
            dim: dict(form.labels[dim]),
            out_dim_b: dict(form.labels[dim]),
        }

        out_info, out_axes = metadata(form, [dim], 'correlation')
        ctx[out_name] = Form(
            data=corr.astype(np.float32),
            dims=[dim, out_dim_b],
            labels=out_labels,
            info=out_info,
            axis_info=out_axes,
        )

        off_diag = corr[~np.eye(n_positions, dtype=bool)]
        finite = off_diag[np.isfinite(off_diag)]

        self._export_data = {
            "dim": dim,
            "metric": metric,
            "output_dims": [dim, out_dim_b],
            "n_positions": int(n_positions),
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "mean": float(finite.mean()) if finite.size else None,
            "n_finite_pairs": int(finite.size),
            "n_total_pairs": int(off_diag.size),
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "metric": metric,
            "n_positions": int(n_positions),
        }

        print(
            f"[correlation] metric='{metric}' dim='{dim}' "
            f"{n_positions} positions -> {corr.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _compute_correlation(metric, X, valid, min_valid):
    n = X.shape[0]
    out = np.full((n, n), np.nan, dtype=np.float64)

    binarize = metric in ("jaccard", "overlap")

    for i in range(n):
        out[i, i] = 1.0
        for j in range(i + 1, n):
            both = valid[i] & valid[j]
            n_both = int(both.sum())
            if n_both < min_valid:
                continue
            xi = X[i, both]
            xj = X[j, both]

            if binarize:
                xi = (xi > 0).astype(np.float64)
                xj = (xj > 0).astype(np.float64)

            value = _pairwise_metric(metric, xi, xj)
            out[i, j] = value
            out[j, i] = value

    return out


def _pairwise_metric(metric, x, y):
    with np.errstate(invalid="ignore", divide="ignore"):
        if metric == "pearson":
            xc = x - x.mean()
            yc = y - y.mean()
            sx = np.sqrt((xc ** 2).sum())
            sy = np.sqrt((yc ** 2).sum())
            if sx < 1e-12 or sy < 1e-12:
                return np.nan
            return float((xc * yc).sum() / (sx * sy))

        if metric == "spearman":
            rx = _rankdata(x)
            ry = _rankdata(y)
            rxc = rx - rx.mean()
            ryc = ry - ry.mean()
            sx = np.sqrt((rxc ** 2).sum())
            sy = np.sqrt((ryc ** 2).sum())
            if sx < 1e-12 or sy < 1e-12:
                return np.nan
            return float((rxc * ryc).sum() / (sx * sy))

        if metric == "kendall":
            return _kendall_tau(x, y)

        if metric == "cosine":
            nx = np.sqrt((x ** 2).sum())
            ny = np.sqrt((y ** 2).sum())
            if nx < 1e-12 or ny < 1e-12:
                return np.nan
            return float((x * y).sum() / (nx * ny))

        if metric == "jaccard":
            inter = float((x * y).sum())
            union = float(((x + y) > 0).sum())
            if union == 0:
                return np.nan
            return inter / union

        if metric == "overlap":
            inter = float((x * y).sum())
            smaller = min(float(x.sum()), float(y.sum()))
            if smaller == 0:
                return np.nan
            return inter / smaller

    raise StepError(
        f"correlation: no implementation for '{metric}'"
    )


def _rankdata(x):
    """Average-rank transform, matching scipy.stats.rankdata."""
    order = np.argsort(x, kind="stable")
    ranks = np.empty_like(order, dtype=np.float64)
    ranks[order] = np.arange(1, len(x) + 1, dtype=np.float64)
    # Average ties.
    i = 0
    n = len(x)
    while i < n:
        j = i
        while j + 1 < n and x[order[j + 1]] == x[order[i]]:
            j += 1
        if j > i:
            avg = (ranks[order[i]] + ranks[order[j]]) / 2.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
        i = j + 1
    return ranks


def _kendall_tau(x, y):
    """Kendall tau-b, matching scipy.stats.kendalltau."""
    try:
        from scipy.stats import kendalltau
    except ImportError as exc:
        raise StepError(
            "correlation/kendall: scipy is required."
        ) from exc
    tau, _ = kendalltau(x, y)
    return float(tau) if np.isfinite(tau) else np.nan
