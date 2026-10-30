"""Procrustes rotation and correlation between two ordinations."""
from __future__ import annotations

import numpy as np

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._stats20_common import scalar_form
from ._ext_common import labels_in_order, require_dims


class ProcrustesStep(Step):
    name = "procrustes"
    title = "Procrustes analysis"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["numpy>=1.26"]
    dependency_imports = ["numpy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("axis_dim", "axis")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("axis_dim", "axis")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "axis_dim": {"type": "string", "default": "axis"},
            "scale": {"type": "boolean", "default": True},
            "output": {"type": "string"},
        },
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        x_form, y_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        axis_dim = ctx.step_params.get("axis_dim", "axis")
        require_dims(x_form, sample_dim, axis_dim, label="procrustes X")
        require_dims(y_form, sample_dim, axis_dim, label="procrustes Y")
        x_samples = labels_in_order(x_form, sample_dim)
        y_samples = labels_in_order(y_form, sample_dim)
        common_samples = [name for name in x_samples if name in y_samples]
        if len(common_samples) < 3:
            raise StepError(f"procrustes: only {len(common_samples)} shared samples")
        x_axes = labels_in_order(x_form, axis_dim)
        y_axes = labels_in_order(y_form, axis_dim)
        common_axes = [name for name in x_axes if name in y_axes]
        if len(common_axes) < 2:
            raise StepError(f"procrustes: only {len(common_axes)} shared axes")
        xi = [x_form.labels[sample_dim][name] for name in common_samples]
        yi = [y_form.labels[sample_dim][name] for name in common_samples]
        xa = [x_form.labels[axis_dim][name] for name in common_axes]
        ya = [y_form.labels[axis_dim][name] for name in common_axes]
        X = np.asarray(x_form.data, dtype=np.float64)[np.ix_(xi, xa)]
        Y = np.asarray(y_form.data, dtype=np.float64)[np.ix_(yi, ya)]
        if not (np.isfinite(X).all() and np.isfinite(Y).all()):
            raise StepError("procrustes: both ordinations must be finite")
        X = X - X.mean(axis=0, keepdims=True)
        Y = Y - Y.mean(axis=0, keepdims=True)
        cross = X.T @ Y
        U, singular, Vt = np.linalg.svd(cross, full_matrices=False)
        A = Vt.T @ U.T
        c = float(np.sum(singular) / np.sum(Y ** 2)) if ctx.step_params.get("scale", True) else 1.0
        Yrot = c * (Y @ A)
        ss = float(np.sum((X - Yrot) ** 2))
        total = float(np.sum(X ** 2))
        r = float(np.sqrt(max(0.0, 1.0 - ss / total))) if total > 0 else float("nan")
        form = scalar_form([r, ss, c, len(common_samples), len(common_axes)],
                           ["r", "ss", "scale", "n", "n_axes"], "procrustes")
        ctx[ctx.step_params.get("output", self.name)] = form
        self._export = {"r": r, "ss": ss, "scale": c,
                        "n": len(common_samples), "n_axes": len(common_axes)}
        print(f"[procrustes] r={r:.6g} ss={ss:.6g}")

    def export(self, ctx: Context) -> dict:
        return self._export
