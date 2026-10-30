"""Variation of information between two cluster-label columns."""
from __future__ import annotations

from collections import Counter

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._cluster_agreement import paired_labels


class VariationOfInformationStep(Step):
    name = "variation_of_information"
    title = "Variation of information"
    category = "Analysis"
    builtin_package = "biopipe-core"
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
            self.name,
        )
        n = len(left)
        joint = Counter(zip(left, right))
        count_a = Counter(left)
        count_b = Counter(right)

        def entropy(counter):
            return float(-sum((value / n) * np.log(value / n) for value in counter.values()))

        h_a = entropy(count_a)
        h_b = entropy(count_b)
        h_joint = entropy(joint)
        if h_joint <= 0:
            raise StepError("variation_of_information: labels have no joint variation")
        mi = 0.0
        for (a, b), count in joint.items():
            p_ij = count / n
            p_i = count_a[a] / n
            p_j = count_b[b] / n
            mi += p_ij * float(np.log(p_ij / (p_i * p_j)))
        vi = float(h_a + h_b - 2.0 * mi)
        nvi = float(vi / h_joint)
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray(
                [
                    [vi],
                    [nvi],
                    [mi],
                    [h_a],
                    [h_b],
                    [h_joint],
                    [float(n)],
                    [float(len(count_a))],
                    [float(len(count_b))],
                ],
                dtype=np.float32,
            ),
            dims=["metric", "value"],
            labels={
                "metric": {
                    "variation_of_information": 0,
                    "normalized_variation_of_information": 1,
                    "mutual_information": 2,
                    "entropy_a": 3,
                    "entropy_b": 4,
                    "joint_entropy": 5,
                    "n_samples": 6,
                    "n_clusters_a": 7,
                    "n_clusters_b": 8,
                },
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "normalization": "joint_entropy"},
        )
        self._export_data = {
            "variation_of_information": vi,
            "normalized_variation_of_information": nvi,
            "mutual_information": mi,
            "entropy_a": h_a,
            "entropy_b": h_b,
            "joint_entropy": h_joint,
            "n_samples": n,
            "n_clusters_a": len(count_a),
            "n_clusters_b": len(count_b),
        }
        print(f"[{self.name}] VI={vi:.4f}, NVI={nvi:.4f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
