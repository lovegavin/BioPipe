"""Student-Newman-Keuls step-down multiple comparisons."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped
from ._posthoc57_common import finite_group_values, pairs


class SnkTestStep(Step):
    """SNK all-pairwise comparisons with a pooled variance and step-down ranges."""

    name = "snk_test"
    title = "Student-Newman-Keuls test"
    category = "Statistics"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.11"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("feature_dim", "feature"), param("sample_dim", "sample")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("group_dim", "feature")]),
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
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("snk_test needs at least two groups")

        rows = []
        comparisons = []
        for feature_index, feature in enumerate(features):
            values = finite_group_values(columns, feature_index, groups, "snk_test")
            if values is None:
                continue
            sizes = np.asarray([value.size for value in values], dtype=np.float64)
            means = np.asarray([value.mean() for value in values], dtype=np.float64)
            variances = np.asarray([value.var(ddof=1) for value in values], dtype=np.float64)
            n_total = sizes.sum()
            df = n_total - len(values)
            if df <= 0:
                continue
            mse = float(np.sum((sizes - 1.0) * variances) / df)
            order = sorted(range(len(values)), key=lambda index: (-means[index], index))
            ranks = [0] * len(values)
            for position, index in enumerate(order):
                ranks[index] = position
            for first, second in pairs(len(values)):
                diff = float(means[first] - means[second])
                variance = mse * 0.5 * (1.0 / sizes[first] + 1.0 / sizes[second])
                if variance <= 0.0:
                    q_value = 0.0 if diff == 0.0 else float("inf")
                    p_value = 1.0 if diff == 0.0 else 0.0
                else:
                    q_value = abs(diff) / np.sqrt(variance)
                    span = abs(ranks[first] - ranks[second]) + 1
                    p_value = float(stats.studentized_range.sf(q_value, span, df))
                span = abs(ranks[first] - ranks[second]) + 1
                comparisons.append(f"{feature}: {groups[first]} vs {groups[second]}")
                rows.append(
                    [
                        diff,
                        q_value,
                        span,
                        p_value,
                        means[first],
                        means[second],
                        sizes[first],
                        sizes[second],
                    ]
                )

        if not rows:
            raise StepError("snk_test: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: index for index, name in enumerate(comparisons)},
                "statistic": {
                    "diff": 0,
                    "q": 1,
                    "span": 2,
                    "p": 3,
                    "mean_a": 4,
                    "mean_b": 5,
                    "n_a": 6,
                    "n_b": 7,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Student-Newman-Keuls",
                "distribution": "studentized_range",
                "adjustment": "step-down",
            },
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
        }
        print(f"[snk_test] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
