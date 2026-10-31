"""EWMA control chart for individual measurements."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._control74_common import moving_range_sigma, single_series


class EwmaChartStep(Step):
    """Exponentially weighted moving-average chart with time-varying limits.

    Sigma is estimated from the average moving range, matching the convention
    used by ``qcc::ewma`` for individual measurements.  The output contains the
    smoothed series, center line, limits and an out-of-control indicator.
    """

    name = "ewma_chart"
    title = "EWMA control chart"
    category = "Statistics"
    builtin_package = "biopipe-core"
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "value_label": {"type": "string"},
            "lambda": {
                "type": "number",
                "exclusiveMinimum": 0,
                "maximum": 1,
                "default": 0.2,
            },
            "nsigmas": {"type": "number", "exclusiveMinimum": 0, "default": 3.0},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        weight = float(ctx.step_params.get("lambda", 0.2))
        nsigmas = float(ctx.step_params.get("nsigmas", 3.0))
        out_name = ctx.step_params.get("output", self.name)
        if not np.isfinite(weight) or weight <= 0 or weight > 1:
            raise StepError(f"{self.name}: lambda must be in (0, 1]")
        if not np.isfinite(nsigmas) or nsigmas <= 0:
            raise StepError(f"{self.name}: nsigmas must be positive")

        values = single_series(inputs[0], sample_dim, feature_dim, value_label, self.name)
        n = int(values.size)
        center = float(np.mean(values))
        sigma = moving_range_sigma(values, self.name)
        smoothed = np.empty(n, dtype=np.float64)
        previous = center
        for i, value in enumerate(values):
            previous = weight * float(value) + (1.0 - weight) * previous
            smoothed[i] = previous

        steps = np.arange(1, n + 1, dtype=np.float64)
        factor = np.sqrt(
            (weight / (2.0 - weight)) * (1.0 - (1.0 - weight) ** (2.0 * steps))
        )
        half_width = nsigmas * sigma * factor
        lower = center - half_width
        upper = center + half_width
        outside = (smoothed < lower) | (smoothed > upper)

        data = np.column_stack(
            [
                smoothed,
                np.full(n, center, dtype=np.float64),
                lower,
                upper,
                np.full(n, sigma, dtype=np.float64),
                outside.astype(np.float64),
            ]
        )
        names = ["ewma", "center", "lcl", "ucl", "std_dev", "out_of_control"]
        samples = [f"s{i}" for i in range(n)]
        form = Form(
            data=data,
            dims=["sample", "statistic"],
            labels={
                "sample": {name: i for i, name in enumerate(samples)},
                "statistic": {name: i for i, name in enumerate(names)},
            },
            info={
                "missing_code": np.nan,
                "method": "EWMA control chart",
                "lambda": weight,
                "nsigmas": nsigmas,
                "n": n,
                "center": center,
                "std_dev": sigma,
                "out_of_control_count": int(outside.sum()),
            },
        )
        form.validate()
        ctx[out_name] = form
        self._export_data = {
            "center": center,
            "std_dev": sigma,
            "lambda": weight,
            "nsigmas": nsigmas,
            "n": n,
            "out_of_control_count": int(outside.sum()),
            "ewma": smoothed.tolist(),
            "lcl": lower.tolist(),
            "ucl": upper.tolist(),
            "out_of_control": outside.astype(int).tolist(),
        }
        print(
            f"[{self.name}] center={center:.6g}, sigma={sigma:.6g}, "
            f"lambda={weight:g}, n={n}, out={int(outside.sum())}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
