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
The output is a dense ``n x n`` matrix. The memory planner reserves its
quadratic workspace/output before execution. An optional ``max_positions``
adds a user-selected count limit; no fixed count cap is imposed by default.

Params:
    dim            : axis to compute distances along (required)
    metric         : metric name (default "euclidean")
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
    "euclidean", "manhattan", "cosine", "correlation",
    "braycurtis", "jaccard", "hamming",
)


class DistanceMatrixStep(Step):
    """Pairwise distance matrix along one axis."""
    provider = 'biopipe-microbiome'
    parameters_file = 'distance_matrix.parameters.json'
    definition = {'protocol_version': 3,
     'id': 'distance_matrix',
     'version': '1.0.0',
     'kind': 'operator',
     'title': 'Distance matrix',
     'description': 'Pairwise distance matrix along one axis.',
     'category': '统计分析',
     'icon': 'Ruler',
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
                                       'representation': {'type': 'string', 'const': 'distance'}},
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
        metric = ctx.step_params.get("metric", "euclidean")
        max_positions = ctx.step_params.get("max_positions")
        if max_positions is not None:
            max_positions = int(max_positions)
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
        if max_positions is not None and max_positions < 1:
            raise StepError(
                f"distance_matrix: max_positions must be >= 1, "
                f"got {max_positions}"
            )

        axis = form.dims.index(dim)
        n_positions = form.data.shape[axis]
        if max_positions is not None and n_positions > max_positions:
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

        out_info, out_axes = metadata(form, [dim], 'distance')
        ctx[out_name] = Form(
            data=dist.astype(np.float32),
            dims=[dim, out_dim_b],
            labels=out_labels,
            info=out_info,
            axis_info=out_axes,
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
