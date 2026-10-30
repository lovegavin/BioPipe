"""Levene test for equality of variances across groups."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._tests50_common import grouped_expression


class LeveneTestStep(Step):
    """Levene test for each feature.

    ``center="mean"`` is Levene's test; ``center="median"`` is the
    Brown-Forsythe variant. The separate ``brown_forsythe`` operator
    exposes the median version with its own name.
    """

    name = "levene_test"
    title = "Levene variance homogeneity test"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    test_label = "Levene"
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
            "center": {
                "type": "string",
                "enum": ["mean", "median"],
                "default": "mean",
            },
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        center = ctx.step_params.get("center", "mean")
        self._run_variance(ctx, inputs, center)

    def _run_variance(self, ctx: Context, inputs, center: str) -> None:
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
            result = stats.levene(*values, center=center)
            n_total = int(sum(value.size for value in values))
            rows.append([
                float(result.statistic),
                float(result.pvalue),
                len(labels) - 1,
                n_total - len(labels),
                len(labels),
                n_total,
            ])
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
                    "df1": 2,
                    "df2": 3,
                    "n_groups": 4,
                    "n": 5,
                },
            },
            info={
                "missing_code": np.nan,
                "test": self.test_label,
                "center": center,
                "n_features": len(kept),
                "n_groups": len(labels),
            },
        )
        self._export_data = {
            "n_features": len(kept),
            "n_groups": len(labels),
            "center": center,
        }
        print(f"[{self.name}] {len(kept)} features, {len(labels)} groups, center={center}")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
