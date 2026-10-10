# src/task/step/steps/pca.py
"""Principal component analysis.

Compresses one dimension of a 2D form into a small number of principal
components. The other dimension becomes the "observation" axis of the
output.

Missing cells are filled with the column mean before standardization.
The output form has no missing values and carries an empty info.

Layout:
    input  : [<dim_to_compress>, <observation_dim>]  (any 2D orientation)
    output : [<observation_dim>, component]
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


class PcaStep(Step):
    """PCA along one dimension.

    Params:
        dim          : dimension to compress
        n_components : number of components to keep (default 10)
        output       : context key for the result (default: step name)
    """

    name = "pca"
    inputs_arity = 1
    outputs = []

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        dim = ctx.step_params["dim"]
        n_components = int(ctx.step_params.get("n_components", 10))
        out_name = ctx.step_params.get("output", self.name)

        if form.data.ndim != 2:
            raise StepError(
                f"pca currently supports only 2D forms. "
                f"Got ndim={form.data.ndim}."
            )
        if dim not in form.dims:
            raise StepError(
                f"Dim '{dim}' is not present. Available: {form.dims}"
            )
        if "missing_code" not in form.info:
            raise StepError(
                f"Form has no info['missing_code']. "
                f"Available: {sorted(form.info)}"
            )

        compress_axis = form.dims.index(dim)
        other_axis = 1 - compress_axis

        X = np.moveaxis(form.data, other_axis, 0).astype(np.float64)

        missing_code = form.info["missing_code"]
        if isinstance(missing_code, float) and np.isnan(missing_code):
            missing = np.isnan(X)
        else:
            missing = X == missing_code

        with np.errstate(invalid="ignore"):
            col_mean = np.nanmean(np.where(missing, np.nan, X), axis=0)
        col_mean = np.where(np.isfinite(col_mean), col_mean, 0.0)

        filled = np.where(missing, col_mean, X)
        centered = filled - col_mean

        with np.errstate(invalid="ignore"):
            col_std = np.nanstd(np.where(missing, np.nan, X), axis=0)
        col_std = np.where(
            np.isfinite(col_std) & (col_std > 1e-12), col_std, 1.0
        )

        scaled = centered / col_std

        k_max = min(scaled.shape)
        k = min(n_components, k_max)
        U, S, _ = np.linalg.svd(scaled, full_matrices=False)
        scores = (U[:, :k] * S[:k]).astype(np.float32)

        obs_dim_name = form.dims[other_axis]
        out_labels = {
            obs_dim_name: dict(form.labels[obs_dim_name]),
            "component": {f"PC{i + 1}": i for i in range(k)},
        }

        ctx[out_name] = Form(
            data=scores,
            dims=[obs_dim_name, "component"],
            labels=out_labels,
            info={},
        )

        explained = (S[:k] ** 2) / float((S ** 2).sum())

        self._export_data = {
            "dim": dim,
            "n_components": k,
            "n_observations": int(scores.shape[0]),
            "explained_variance_ratio": [
                float(v) for v in explained
            ],
            "singular_values": [float(v) for v in S[:k]],
        }

        ctx.metadata.setdefault(self.name, {})[out_name] = {
            "dim": dim,
            "n_components": k,
            "explained_variance_ratio": [
                float(v) for v in explained
            ],
        }

        print(
            f"[pca] compressed '{dim}' -> {k} components, "
            f"PC1={explained[0]:.3f}, PC2={explained[1]:.3f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data