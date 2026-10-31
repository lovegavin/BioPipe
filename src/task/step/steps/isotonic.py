"""Isotonic regression."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats21_common import numeric_column, table_frame

_STATISTICS = ["x", "y", "fitted", "residual"]


class IsotonicStep(Step):
    """Fit a monotone (increasing or decreasing) least-squares curve."""

    name = "isotonic"
    title = "Isotonic regression"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(
            ndim=2,
            dims=[param("sample_dim", "sample"), param("feature_dim", "feature")],
        )
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
            "feature_dim": {"type": "string", "default": "feature"},
            "x_label": {"type": "string"},
            "y_label": {"type": "string"},
            "increasing": {"type": "boolean", "default": True},
            "out_of_bounds": {
                "type": "string",
                "enum": ["clip", "nan", "raise"],
                "default": "clip",
            },
            "output": {"type": "string"},
        },
        "required": ["x_label", "y_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.isotonic import IsotonicRegression

        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x_label = ctx.step_params["x_label"]
        y_label = ctx.step_params["y_label"]
        increasing = bool(ctx.step_params.get("increasing", True))
        out_of_bounds = ctx.step_params.get("out_of_bounds", "clip")
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(inputs[0], sample_dim, feature_dim, self.name)
        x = numeric_column(frame, x_label, self.name)
        y = numeric_column(frame, y_label, self.name)
        samples = np.asarray(frame["__sample__"].to_numpy(), dtype=object)
        keep = np.isfinite(x) & np.isfinite(y)
        if not keep.any():
            raise StepError(f"{self.name}: no finite (x, y) pairs")
        x = np.asarray(x[keep], dtype=np.float64)
        y = np.asarray(y[keep], dtype=np.float64)
        samples = samples[keep]
        n = int(x.size)
        if n < 3:
            raise StepError(f"{self.name}: need at least 3 finite pairs")
        if np.unique(x).size != n:
            raise StepError(f"{self.name}: x values must be unique")
        if float(np.ptp(x)) <= 0:
            raise StepError(f"{self.name}: x has zero range")

        order = np.argsort(x, kind="mergesort")
        x = x[order]
        y = y[order]
        samples = samples[order]
        try:
            model = IsotonicRegression(
                increasing=increasing,
                out_of_bounds=out_of_bounds,
            )
            fitted = np.asarray(model.fit_transform(x, y), dtype=np.float64)
        except (ValueError, TypeError) as exc:
            raise StepError(f"{self.name}: isotonic fit failed: {exc}") from exc
        if not np.isfinite(fitted).all():
            raise StepError(f"{self.name}: fitted values are not finite")

        table = np.column_stack([x, y, fitted, y - fitted])
        ctx[out_name] = Form(
            data=table,
            dims=["sample", "statistic"],
            labels={
                "sample": {
                    str(name): index for index, name in enumerate(samples)
                },
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info={
                "method": "isotonic regression",
                "increasing": increasing,
                "out_of_bounds": out_of_bounds,
                "n": n,
                "n_blocks": int(np.unique(np.round(fitted, 12)).size),
            },
        )
        self._export = {
            "samples": [str(value) for value in samples],
            "x": [float(value) for value in x],
            "y": [float(value) for value in y],
            "fitted": [float(value) for value in fitted],
            "residual": [float(value) for value in y - fitted],
            "thresholds_x": [
                float(value) for value in np.asarray(model.X_thresholds_)
            ],
            "thresholds_y": [
                float(value) for value in np.asarray(model.y_thresholds_)
            ],
            "increasing": increasing,
            "n": n,
        }
        print(f"[{self.name}] isotonic n={n}, increasing={increasing}")

    def export(self, ctx: Context) -> dict:
        return self._export
