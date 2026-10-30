"""Sen's slope and Theil-Sen intercept from paired observations."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class SenSlopeStep(Step):
    """Sen's median pairwise slope with a Theil-Sen confidence interval.

    ``scipy.stats.theilslopes`` is the reference implementation: it forms all
    pairwise slopes, takes the median, and uses the rank-based confidence
    interval.
    """

    name = "sen_slope"
    title = "Sen's slope"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 1
    outputs = []
    output_parameter = "output"
    input_contracts = [port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")])]
    output_contract = {"mode": "declare", "schema": {
        "ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "x_label": {"type": "string", "title": "自变量字段"},
            "y_label": {"type": "string", "title": "因变量字段"},
            "confidence": {"type": "number", "default": 0.95, "minimum": 0.0, "maximum": 1.0, "title": "置信水平"},
            "output": {"type": "string"},
        },
        "required": ["x_label", "y_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        x_label = ctx.step_params["x_label"]
        y_label = ctx.step_params["y_label"]
        confidence = float(ctx.step_params.get("confidence", 0.95))
        out_name = ctx.step_params.get("output", self.name)
        if not 0.0 < confidence < 1.0:
            raise StepError("sen_slope: confidence must be strictly between 0 and 1")

        frame = table_frame(form, sample_dim, feature_dim, "sen_slope")
        x = np.asarray(numeric_column(frame, x_label, "sen_slope"), dtype=np.float64)
        y = np.asarray(numeric_column(frame, y_label, "sen_slope"), dtype=np.float64)
        mask = np.isfinite(x) & np.isfinite(y)
        x = x[mask]
        y = y[mask]
        if x.size < 3:
            raise StepError("sen_slope: need at least three complete pairs")
        if np.unique(x).size < 2:
            raise StepError("sen_slope: x values must not be constant")
        result = stats.theilslopes(y, x, alpha=confidence)
        slope = float(result.slope)
        intercept = float(result.intercept)
        ci_low = float(result.low_slope)
        ci_high = float(result.high_slope)
        out = scalar_form(
            [slope, intercept, ci_low, ci_high, float(x.size), confidence],
            ["slope", "intercept", "ci_low", "ci_high", "n", "confidence"],
            "sen_slope",
        )
        out.info.update({"method": "Theil-Sen / Sen median slope"})
        ctx[out_name] = out
        self._export_data = {
            "slope": slope, "intercept": intercept, "ci_low": ci_low,
            "ci_high": ci_high, "n": int(x.size), "confidence": confidence,
        }
        print(f"[sen_slope] slope={slope:.6g}, CI=({ci_low:.6g}, {ci_high:.6g})")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
