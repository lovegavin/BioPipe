"""Pairwise confusion counts for two cluster-label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import pair_confusion_matrix

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class PairConfusionMatrixStep(Step):
    """Pair-count confusion matrix behind Rand-type agreement scores."""

    name = "pair_confusion_matrix"
    title = "Pair confusion matrix"
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
            "pair_confusion_matrix",
        )
        n_a, n_b = len(set(left)), len(set(right))
        if n_a < 2 or n_b < 2:
            raise StepError(
                "pair_confusion_matrix: need at least two clusters in each partition"
            )
        matrix = pair_confusion_matrix(left, right)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=matrix.astype(np.float32),
            dims=["pair_a", "pair_b"],
            labels={
                "pair_a": {
                    "same_cluster": 0,
                    "different_cluster": 1,
                },
                "pair_b": {
                    "same_label": 0,
                    "different_label": 1,
                },
            },
            info={
                "missing_code": np.nan,
                "n_samples": len(left),
                "n_clusters_a": n_a,
                "n_clusters_b": n_b,
            },
        )
        self._export_data = {
            "same_cluster_same_label": int(matrix[0, 0]),
            "same_cluster_different_label": int(matrix[0, 1]),
            "different_cluster_same_label": int(matrix[1, 0]),
            "different_cluster_different_label": int(matrix[1, 1]),
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
        }
        print(f"[pair_confusion_matrix] {matrix.tolist()}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
