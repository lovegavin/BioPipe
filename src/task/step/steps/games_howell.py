"""Games-Howell all-pairwise comparisons with Welch degrees of freedom."""
from __future__ import annotations

import numpy as np
from scipy import stats

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step

from ._matrix_common import grouped


class GamesHowellStep(Step):
    """All-pairwise Games-Howell comparisons for every feature.

    The studentized range statistic uses unequal variances and a Welch
    degrees-of-freedom approximation, matching ``PMCMRplus::gamesHowellTest``.
    """

    name = "games_howell"
    title = "Games-Howell post-hoc test"
    category = "Analysis"
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
            raise StepError("games_howell needs at least two groups")
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = []
            for col in columns:
                value = np.asarray(col[:, i], dtype=np.float64)
                value = value[np.isfinite(value)]
                if value.size < 2:
                    values = []
                    break
                values.append(value)
            if len(values) < 2:
                continue
            sizes = np.asarray([value.size for value in values], dtype=np.float64)
            means = np.asarray([value.mean() for value in values], dtype=np.float64)
            variances = np.asarray([value.var(ddof=1) for value in values], dtype=np.float64)
            k = len(values)
            for b in range(1, k):
                for a in range(b):
                    diff = float(means[a] - means[b])
                    variance = variances[a] / sizes[a] + variances[b] / sizes[b]
                    if variance <= 0.0:
                        q_value = 0.0 if diff == 0.0 else float("inf")
                        p_value = 1.0 if diff == 0.0 else 0.0
                        df = float("nan")
                    else:
                        q_value = abs(diff) / np.sqrt(variance) * np.sqrt(2.0)
                        df = variance**2 / (
                            variances[a] ** 2 / (sizes[a] ** 2 * (sizes[a] - 1.0))
                            + variances[b] ** 2 / (sizes[b] ** 2 * (sizes[b] - 1.0))
                        )
                        p_value = float(stats.studentized_range.sf(q_value, k, df))
                    comparisons.append(f"{feature}: {groups[a]} vs {groups[b]}")
                    rows.append([
                        diff,
                        q_value,
                        df,
                        p_value,
                        means[a],
                        means[b],
                        sizes[a],
                        sizes[b],
                    ])

        if not rows:
            raise StepError("games_howell: no feature had enough finite group data")
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {
                    "diff": 0,
                    "q": 1,
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
                "method": "Games-Howell",
                "distribution": "studentized_range",
            },
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
        }
        print(f"[games_howell] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
