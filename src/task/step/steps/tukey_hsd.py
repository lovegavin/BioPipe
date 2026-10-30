"""Tukey HSD post-hoc pairwise comparisons."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import grouped


class TukeyHsdStep(Step):
    """Tukey HSD across groups for every feature."""

    name = "tukey_hsd"
    title = "Tukey HSD"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["statsmodels>=0.14"]
    dependency_imports = ["statsmodels"]
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
            "alpha": {"type": "number", "minimum": 0.001, "maximum": 0.5, "default": 0.05},
            "output": {"type": "string"},
        },
        "required": ["group_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from statsmodels.stats.multicomp import pairwise_tukeyhsd

        data, meta = inputs
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        group_dim = ctx.step_params.get("group_dim", "sample")
        columns, features, groups = grouped(
            data, meta, sample_dim, feature_dim, group_dim, ctx.step_params["group_label"]
        )
        if len(groups) < 2:
            raise StepError("tukey_hsd needs at least two groups")
        alpha = float(ctx.step_params.get("alpha", 0.05))
        rows = []
        comparisons = []
        for i, feature in enumerate(features):
            values = [col[:, i] for col in columns]
            all_values = np.concatenate(values)
            all_groups = np.concatenate([
                np.full(len(v), g, dtype=object) for g, v in zip(groups, values)
            ])
            result = pairwise_tukeyhsd(all_values, all_groups, alpha=alpha)
            table = result.summary()
            for row in table.data[1:]:
                comparisons.append(f"{feature}: {row[0]} vs {row[1]}")
                rows.append([
                    float(row[2]), float(row[3]), float(row[4]),
                    float(row[5]), 1.0 if bool(row[6]) else 0.0,
                ])
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(rows, dtype=np.float32),
            dims=["comparison", "statistic"],
            labels={
                "comparison": {name: i for i, name in enumerate(comparisons)},
                "statistic": {"diff": 0, "P": 1, "CI_low": 2, "CI_high": 3, "reject": 4},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_features": len(features),
            "n_groups": len(groups),
            "n_comparisons": len(comparisons),
            "alpha": alpha,
        }
        print(f"[tukey_hsd] {len(features)} features, {len(comparisons)} comparisons")

    def export(self, ctx: Context) -> dict:
        return self._export_data
