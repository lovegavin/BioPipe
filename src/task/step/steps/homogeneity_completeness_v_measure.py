"""Homogeneity, completeness, and V-measure for two label columns."""
from __future__ import annotations

import numpy as np
from sklearn.metrics import homogeneity_completeness_v_measure

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class HomogeneityCompletenessVMeasureStep(Step):
    """Three entropy-based agreement scores for two partitions."""

    name = "homogeneity_completeness_v_measure"
    title = "Homogeneity, completeness, V-measure"
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
            "beta": {"type": "number", "default": 1.0, "exclusiveMinimum": 0.0},
            "output": {"type": "string"},
        },
        "required": ["label_a", "label_b"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        first, second = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        beta = float(ctx.step_params.get("beta", 1.0))
        left, right = paired_labels(
            first,
            second,
            sample_dim,
            label_dim,
            ctx.step_params["label_a"],
            ctx.step_params["label_b"],
            "homogeneity_completeness_v_measure",
        )
        n_a, n_b = len(set(left)), len(set(right))
        if n_a < 2 or n_b < 2:
            raise StepError(
                "homogeneity_completeness_v_measure: need at least two clusters in each partition"
            )
        homogeneity, completeness, v_measure = homogeneity_completeness_v_measure(
            left, right, beta=beta
        )
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(
                [
                    [homogeneity],
                    [completeness],
                    [v_measure],
                    [len(left)],
                    [n_a],
                    [n_b],
                ],
                dtype=np.float32,
            ),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "homogeneity": 0,
                    "completeness": 1,
                    "v_measure": 2,
                    "n_samples": 3,
                    "n_clusters_a": 4,
                    "n_clusters_b": 5,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "beta": beta},
        )
        self._export_data = {
            "homogeneity": float(homogeneity),
            "completeness": float(completeness),
            "v_measure": float(v_measure),
            "beta": beta,
            "n_samples": len(left),
            "n_clusters_a": n_a,
            "n_clusters_b": n_b,
        }
        print(
            f"[homogeneity_completeness_v_measure] h={homogeneity:.4f}, "
            f"c={completeness:.4f}, v={v_measure:.4f}"
        )

    def export(self, ctx: Context) -> dict:
        return self._export_data
