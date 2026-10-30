"""Canonical correlations between two multivariate tables."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._ext_common import make_form
from ._multivariate35_common import aligned_matrices


class CanonicalCorrelationStep(Step):
    """Canonical correlations via reduced QR and an SVD cross-product."""

    name = "canonical_correlation"
    title = "Canonical correlation"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("x_dim", "x")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("y_dim", "y")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {
            "ndim": 2,
            "numeric": True,
            "info_open": True,
            "axis_info_open": True,
        },
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "x_dim": {"type": "string", "default": "x"},
            "y_dim": {"type": "string", "default": "y"},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form_x, form_y = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        x_dim = ctx.step_params.get("x_dim", "x")
        y_dim = ctx.step_params.get("y_dim", "y")
        out_name = ctx.step_params.get("output", self.name)
        x_names, y_names, X, Y = aligned_matrices(
            form_x, form_y, sample_dim, x_dim, y_dim, "canonical_correlation"
        )
        X = X - X.mean(axis=0, keepdims=True)
        Y = Y - Y.mean(axis=0, keepdims=True)
        qx = np.linalg.qr(X, mode="reduced")[0]
        qy = np.linalg.qr(Y, mode="reduced")[0]
        _, singular, _ = np.linalg.svd(qx.T @ qy, full_matrices=False)
        count = min(X.shape[1], Y.shape[1])
        correlations = np.clip(singular[:count], 0.0, 1.0)
        if not np.isfinite(correlations).all():
            raise StepError("canonical_correlation: correlations are not finite")

        values = np.column_stack([correlations, np.square(correlations)])
        out = make_form(
            values.tolist(),
            ["component", "statistic"],
            {
                "component": {str(index + 1): index for index in range(count)},
                "statistic": {"correlation": 0, "squared": 1},
            },
        )
        out.info.update(
            {
                "missing_code": np.nan,
                "method": "qr_svd",
                "n_subjects": int(X.shape[0]),
                "n_x": int(X.shape[1]),
                "n_y": int(Y.shape[1]),
                "x_columns": x_names,
                "y_columns": y_names,
            }
        )
        ctx[out_name] = out
        self._export_data = {
            "correlations": [float(value) for value in correlations],
            "squared": [float(value) for value in np.square(correlations)],
            "n_subjects": int(X.shape[0]),
            "n_x": int(X.shape[1]),
            "n_y": int(Y.shape[1]),
            "x_columns": x_names,
            "y_columns": y_names,
        }
        print(
            "[canonical_correlation] "
            + ", ".join(f"{value:.6f}" for value in correlations)
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
