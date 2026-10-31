"""Fowlkes-Mallows index for two cluster-label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import fowlkes_mallows_score

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class FowlkesMallowsStep(Step):
    """Geometric mean of pairwise precision and recall between two partitions."""

    name = "fowlkes_mallows"
    title = "Fowlkes-Mallows index"
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
            "output": {"type": "string"},
        },
        "required": ["label_a", "label_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        left, right = paired_labels(
            first,
            second,
            sample_dim,
            label_dim,
            ctx.step_params["label_a"],
            ctx.step_params["label_b"],
            "fowlkes_mallows",
        )
        n_a, n_b = len(set(left)), len(set(right))
        if n_a < 2 or n_b < 2:
            raise StepError("fowlkes_mallows: need at least two clusters in each partition")
        score = float(fowlkes_mallows_score(left, right))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(left)], [n_a], [n_b]], dtype=np.float32),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "fowlkes_mallows": 0,
                    "n_samples": 1,
                    "n_clusters_a": 2,
                    "n_clusters_b": 3,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "fowlkes_mallows": score,
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
        }
        print(f"[fowlkes_mallows] {score:.4f}, k={n_a}/{n_b}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
