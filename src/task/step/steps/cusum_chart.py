"""Two-sided tabular CUSUM control chart for individual measurements."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._control74_common import moving_range_sigma, single_series


class CusumChartStep(Step):
    """Tabular CUSUM chart with a moving-range sigma estimate.

    The chart is a deterministic, table-valued control chart: each output row
    contains the upper/lower CUSUM statistic and the decision limit.  It does
    not draw a plot, so the result can be inspected or plotted by the caller.
    """

    name = "cusum_chart"
    title = "CUSUM control chart"
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
            "decision_interval": {"type": "number", "exclusiveMinimum": 0, "default": 5.0},
            "se_shift": {"type": "number", "exclusiveMinimum": 0, "default": 1.0},
            "output": {"type": "string"},
        },
        "required": ["value_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        decision_interval = float(ctx.step_params.get("decision_interval", 5.0))
        se_shift = float(ctx.step_params.get("se_shift", 1.0))
        out_name = ctx.step_params.get("output", self.name)
        if not np.isfinite(decision_interval) or decision_interval <= 0:
            raise StepError(f"{self.name}: decision_interval must be positive")
        if not np.isfinite(se_shift) or se_shift <= 0:
            raise StepError(f"{self.name}: se_shift must be positive")

        values = single_series(inputs[0], sample_dim, feature_dim, value_label, self.name)
        n = int(values.size)
        center = float(np.mean(values))
        sigma = moving_range_sigma(values, self.name)
        half_shift = 0.5 * se_shift
        positive = np.zeros(n, dtype=np.float64)
        negative = np.zeros(n, dtype=np.float64)
        for i, value in enumerate(values):
            z = (float(value) - center) / sigma
            previous_positive = positive[i - 1] if i else 0.0
            previous_negative = negative[i - 1] if i else 0.0
            positive[i] = max(0.0, previous_positive + z - half_shift)
            negative[i] = min(0.0, previous_negative + z + half_shift)

        outside = (positive > decision_interval) | (negative < -decision_interval)
        data = np.column_stack(
            [
                positive,
                negative,
                np.full(n, center, dtype=np.float64),
                np.full(n, sigma, dtype=np.float64),
                np.full(n, decision_interval, dtype=np.float64),
                outside.astype(np.float64),
            ]
        )
        names = [
            "cusum_pos",
            "cusum_neg",
            "center",
            "std_dev",
            "limit",
            "out_of_control",
        ]
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
                "method": "two-sided tabular CUSUM",
                "decision_interval": decision_interval,
                "se_shift": se_shift,
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
            "decision_interval": decision_interval,
            "se_shift": se_shift,
            "n": n,
            "out_of_control_count": int(outside.sum()),
            "cusum_pos": positive.tolist(),
            "cusum_neg": negative.tolist(),
            "out_of_control": outside.astype(int).tolist(),
        }
        print(
            f"[{self.name}] center={center:.6g}, sigma={sigma:.6g}, "
            f"n={n}, out={int(outside.sum())}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
