"""Tamhane T2 all-pairwise comparisons."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped
from ._posthoc57_common import finite_group_values, pairs


class TamhaneT2Step(Step):
    """Tamhane T2 comparisons with Welch degrees of freedom and Sidak correction."""

    name = "tamhane_t2"
    title = "Tamhane T2 test"
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
            raise StepError("tamhane_t2 needs at least two groups")

        rows = []
        comparisons = []
        pair_count = len(groups) * (len(groups) - 1) / 2.0
        for feature_index, feature in enumerate(features):
            values = finite_group_values(columns, feature_index, groups, "tamhane_t2")
            if values is None:
                continue
            sizes = np.asarray([value.size for value in values], dtype=np.float64)
            means = np.asarray([value.mean() for value in values], dtype=np.float64)
            variances = np.asarray([value.var(ddof=1) for value in values], dtype=np.float64)
            for first, second in pairs(len(values)):
                diff = float(means[first] - means[second])
                variance = float(
                    variances[first] / sizes[first] + variances[second] / sizes[second]
                )
                if variance <= 0.0:
                    statistic = 0.0 if diff == 0.0 else float("inf")
                    p_value = 1.0 if diff == 0.0 else 0.0
                    df = sizes[first] + sizes[second] - 2.0
                else:
                    statistic = abs(diff) / np.sqrt(variance)
                    first_term = variances[first] ** 2 / (
                        sizes[first] ** 2 * (sizes[first] - 1.0)
                    )
                    second_term = variances[second] ** 2 / (
                        sizes[second] ** 2 * (sizes[second] - 1.0)
                    )
                    df = variance**2 / (first_term + second_term)
                    raw = 2.0 * stats.t.sf(abs(statistic), df)
                    p_value = -np.expm1(pair_count * np.log1p(-min(raw, 1.0)))
                comparisons.append(f"{feature}: {groups[first]} vs {groups[second]}")
                rows.append(
                    [
                        diff,
                        statistic,
                        df,
                        p_value,
                        means[first],
                        means[second],
                        sizes[first],
                        sizes[second],
                    ]
                )

        if not rows:
            raise StepError("tamhane_t2: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: index for index, name in enumerate(comparisons)},
                "statistic": {
                    "diff": 0,
                    "t": 1,
                    "df": 2,
                    "p": 3,
                    "mean_a": 4,
                    "mean_b": 5,
                    "n_a": 6,
                    "n_b": 7,
                },
            },
            info={
                "missing_code": np.nan,
                "method": "Tamhane T2",
                "welch": True,
                "adjustment": "Sidak",
                "n_comparisons": int(pair_count),
            },
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": int(pair_count),
        }
        print(f"[tamhane_t2] {len(features)} features, {int(pair_count)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
