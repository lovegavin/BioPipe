"""Mood's median test for independent groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._stats20_common import scalar_form
from ._stats21_common import numeric_column, table_frame


class MoodMedianTestStep(Step):
    """Mood's median test for equal group medians.

    Counts observations above/below the pooled median and applies a
    chi-square (or Fisher exact) test. ``scipy.stats.median_test`` also
    supports the ties modes below/above/ignore and a Yates correction.
    """

    name = "mood_median_test"
    title = "Mood's median test"
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
            "value_label": {"type": "string", "title": "数值字段"},
            "group_label": {"type": "string", "title": "分组字段"},
            "ties": {"type": "string", "enum": ["below", "above", "ignore"], "default": "below", "title": "并列值处理"},
            "correction": {"type": "boolean", "default": True, "title": "Yates 连续性校正"},
            "output": {"type": "string"},
        },
        "required": ["value_label", "group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        form = inputs[0]
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        value_label = ctx.step_params["value_label"]
        group_label = ctx.step_params["group_label"]
        ties = ctx.step_params.get("ties", "below")
        correction = bool(ctx.step_params.get("correction", True))
        out_name = ctx.step_params.get("output", self.name)

        frame = table_frame(form, sample_dim, feature_dim, "mood_median_test")
        if group_label not in frame.columns:
            raise StepError(f"mood_median_test: group column {group_label!r} not found")
        values = np.asarray(numeric_column(frame, value_label, "mood_median_test"), dtype=np.float64)
        groups = frame[group_label].astype(str).to_numpy()
        names = list(dict.fromkeys(groups.tolist()))
        if len(names) < 2:
            raise StepError("mood_median_test: need at least two groups")
        samples = [values[(groups == name) & np.isfinite(values)] for name in names]
        if any(sample.size == 0 for sample in samples):
            raise StepError("mood_median_test: every group needs at least one finite value")
        if np.unique(values[np.isfinite(values)]).size < 2:
            raise StepError("mood_median_test: values are constant")
        try:
            result = stats.median_test(*samples, ties=ties, correction=correction)
        except ValueError as exc:
            raise StepError(f"mood_median_test: {exc}") from exc
        statistic = float(result.statistic)
        p_value = float(result.pvalue)
        median = float(result.median)
        n = int(sum(sample.size for sample in samples))
        out = scalar_form(
            [statistic, p_value, median, float(len(samples)), float(n)],
            ["statistic", "p", "median", "n_groups", "n"],
            "mood_median_test",
        )
        out.info.update({
            "ties": ties, "correction": correction,
            "groups": {name: int(sample.size) for name, sample in zip(names, samples)},
        })
        ctx[out_name] = out
        self._export_data = {
            "statistic": statistic, "p": p_value, "median": median,
            "n_groups": len(samples), "n": n, "ties": ties,
            "correction": correction, "groups": {name: int(sample.size) for name, sample in zip(names, samples)},
        }
        print(f"[mood_median_test] statistic={statistic:.6g}, p={p_value:.6g}, groups={len(samples)}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
