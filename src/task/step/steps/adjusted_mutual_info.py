"""Adjusted mutual information for two cluster-label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import adjusted_mutual_info_score

from src.core import Form
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class AdjustedMutualInfoStep(Step):
    """Adjusted mutual information between two partitions."""

    name = "adjusted_mutual_info"
    title = "Adjusted mutual information"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
    ]
    output_contract = {
        "mode": "declare",
        "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True},
    }
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "label_dim": {"type": "string", "default": "label"},
            "label_a": {"type": "string"},
            "label_b": {"type": "string"},
            "average_method": {
                "type": "string",
                "enum": ["max", "arithmetic", "geometric", "min"],
                "default": "max",
            },
            "output": {"type": "string"},
        },
        "required": ["label_a", "label_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        method = ctx.step_params.get("average_method", "max")
        left, right = paired_labels(
            first,
            second,
            sample_dim,
            label_dim,
            ctx.step_params["label_a"],
            ctx.step_params["label_b"],
            "adjusted_mutual_info",
        )
        score = float(adjusted_mutual_info_score(left, right, average_method=method))
        n_a, n_b = len(set(left)), len(set(right))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(left)], [n_a], [n_b]], dtype=np.float32),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "adjusted_mutual_info": 0,
                    "n_samples": 1,
                    "n_clusters_a": 2,
                    "n_clusters_b": 3,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "average_method": method},
        )
        self._export_data = {
            "adjusted_mutual_info": score,
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
            "average_method": method,
        }
        print(f"[adjusted_mutual_info] {score:.4f} ({method})")

    def export(self, ctx: Context) -> dict:
        return self._export_data
