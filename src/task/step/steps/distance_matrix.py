# src/task/step/steps/distance_matrix.py
"""Pairwise distance matrix along one axis of a form.

Computes the distance between every pair of positions along ``dim``,
using the values across the other axes as features. The output is a
square form with the same labels on both axes.

Output dims
-----------
    dims = [dim, f"{dim}_b"]

Both axes carry the same labels, in the same order. ``form.data[i, j]``
is the distance between position ``i`` and position ``j``.

Metrics
-------
    euclidean     L2 distance
    manhattan     L1 distance
    cosine        1 - cosine similarity
    correlation   1 - Pearson correlation
    braycurtis    sum(|a - b|) / sum(a + b)
    jaccard       1 - |A and B| / |A or B|, on binarized (>0) values
    hamming       fraction of positions where a != b, after
                  binarization

Missing values
--------------
Missing cells are filled with 0 before the computation. This is the
correct interpretation for abundance matrices (an unobserved
species has zero abundance), and it also matches how ``braycurtis``
and ``jaccard`` are normally applied.

Size guard
----------
The output is a dense ``n x n`` matrix. To avoid accidental
allocation of hundreds of gigabytes, the operator refuses to run if
``n > max_positions`` (default 10000). Raise it explicitly if you
know what you are doing.

Params:
    dim            : axis to compute distances along (required)
    metric         : metric name (default "euclidean")
    max_positions  : refuse if dim has more positions than this
                     (default 10000)
    output         : context key for the result (default: step name)
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


_METRICS = (
    "euclidean", "manhattan", "cosine", "correlation",
    "braycurtis", "jaccard", "hamming",
)


class DistanceMatrixStep(Step):
    """Pairwise distance matrix along one axis."""

    name = "distance_matrix"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params.get("dim")
        metric = ctx.step_params.get("metric", "euclidean")
        max_positions = int(
            ctx.step_params.get("max_positions", 10000)
        )
        out_name = ctx.step_params.get("output", self.name)

        if not dim:
            raise StepError("distance_matrix: 'dim' is required")
        if dim not in form.dims:
            raise StepError(
                f"distance_matrix: dim '{dim}' not present. "
                f"Available: {form.dims}"
            )
        if metric not in _METRICS:
            raise StepError(
                f"distance_matrix: metric must be one of "
                f"{list(_METRICS)}, got {metric!r}"
            )
        if max_positions < 1:
            raise StepError(
                f"distance_matrix: max_positions must be >= 1, "
                f"got {max_positions}"
            )

        axis = form.dims.index(dim)
        n_positions = form.data.shape[axis]
        if n_positions > max_positions:
            raise StepError(
                f"distance_matrix: dim '{dim}' has {n_positions} "
                f"positions, which would produce a "
                f"{n_positions}x{n_positions} dense matrix. "
                f"Raise 'max_positions' explicitly if you need this."
            )
        if n_positions < 2:
            raise StepError(
                f"distance_matrix: dim '{dim}' has only "
                f"{n_positions} position(s)"
            )

        moved = np.moveaxis(form.data, axis, 0).astype(np.float64)
        flat = moved.reshape(n_positions, -1)

        missing_code = form.info.get("missing_code", np.nan)
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(flat)
        else:
            missing = flat == missing_code
        filled = np.where(missing, 0.0, flat)

        dist = _compute_distance(metric, filled)

        # Symmetrize (should already be symmetric) and zero the
        # diagonal.
        dist = 0.5 * (dist + dist.T)
        np.fill_diagonal(dist, 0.0)

        out_dim_b = f"{dim}_b"
        out_labels = {
            dim: dict(form.labels[dim]),
            out_dim_b: dict(form.labels[dim]),
        }

        ctx[out_name] = Form(
            data=dist.astype(np.float32),
            dims=[dim, out_dim_b],
            labels=out_labels,
            info={"missing_code": np.nan},
        )

        finite = dist[np.isfinite(dist)]
        self._export_data = {
            "dim": dim,
            "metric": metric,
            "output_dims": [dim, out_dim_b],
            "n_positions": int(n_positions),
            "min": float(finite.min()) if finite.size else None,
            "max": float(finite.max()) if finite.size else None,
            "mean": float(finite.mean()) if finite.size else None,
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "metric": metric,
            "n_positions": int(n_positions),
        }

        print(
            f"[distance_matrix] metric='{metric}' dim='{dim}' "
            f"{n_positions} positions -> {dist.shape}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data


def _compute_distance(metric: str, X: np.ndarray) -> np.ndarray:
    try:
        from scipy.spatial.distance import cdist
    except ImportError as exc:
        raise StepError(
            "distance_matrix: scipy is required."
        ) from exc

    if metric in ("jaccard", "hamming"):
        X = (X > 0).astype(np.float64)

    if metric == "euclidean":
        return cdist(X, X, metric="euclidean")
    if metric == "manhattan":
        return cdist(X, X, metric="cityblock")
    if metric == "cosine":
        return cdist(X, X, metric="cosine")
    if metric == "correlation":
        return cdist(X, X, metric="correlation")
    if metric == "braycurtis":
        # scipy's braycurtis produces NaN when both vectors are zero
        # at every position; guard against that.
        with np.errstate(invalid="ignore", divide="ignore"):
            D = cdist(X, X, metric="braycurtis")
        D = np.where(np.isfinite(D), D, 0.0)
        return D
    if metric == "jaccard":
        with np.errstate(invalid="ignore", divide="ignore"):
            D = cdist(X, X, metric="jaccard")
        D = np.where(np.isfinite(D), D, 0.0)
        return D
    if metric == "hamming":
        return cdist(X, X, metric="hamming")

    raise StepError(
        f"distance_matrix: no implementation for '{metric}'"
    )