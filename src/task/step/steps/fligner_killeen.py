"""Fligner-Killeen test for homogeneity of variances across groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._tests50_common import grouped_expression


class FlignerKilleenStep(Step):
    """Fligner-Killeen median-centered rank test for each feature."""

    name = "fligner_killeen"
    title = "Fligner-Killeen variance homogeneity test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("group_dim", "sample"), param("feature_dim", "feature")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "feature_dim": {"type": "string", "default": "feature"},
            "sample_dim": {"type": "string", "default": "sample"},
            "group_dim": {"type": "string", "default": "sample"},
            "group_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        X, features, _, groups, labels = grouped_expression(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        group_array = np.asarray(groups)
        rows = []
        kept = []
        for j, feature in enumerate(features):
            values = []
            for label in labels:
                column = X[group_array == label, j]
                column = column[np.isfinite(column)]
                if column.size < 2:
                    values = []
                    break
                values.append(column)
            if not values:
                continue
            centered = np.concatenate([value - np.median(value) for value in values])
            n = centered.size
            if n < 3:
                continue
            scores = stats.norm.ppf((1.0 + stats.rankdata(np.abs(centered)) / (n + 1.0)) / 2.0)
            scores = scores - scores.mean()
            variance = float(np.sum(scores * scores) / (n - 1))
            if variance <= 0:
                continue
            statistic = float(sum(value.size * np.mean(scores[offset:offset + value.size]) ** 2
                                  for value, offset in _offsets(values)) / variance)
            df = len(values) - 1
            p_value = float(stats.chi2.sf(statistic, df))
            rows.append([statistic, p_value, float(df), float(len(values)), float(n)])
            kept.append(feature)

        if not rows:
            raise StepError(f"{self.name}: no feature had two finite values in every group")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["feature", "statistic"],
            labels={
                "feature": {name: i for i, name in enumerate(kept)},
                "statistic": {
                    "statistic": 0,
                    "p": 1,
                    "df": 2,
                    "n_groups": 3,
                    "n": 4,
                },
            },
            info={
                "missing_code": np.nan,
                "test": "Fligner-Killeen",
                "center": "median",
                "n_features": len(kept),
                "n_groups": len(labels),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(labels),
            "test": "Fligner-Killeen",
        }
        print(f"[{self.name}] {len(kept)} features, {len(labels)} groups")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})


def _offsets(values):
    start = 0
    for value in values:
        yield value, start
        start += value.size
