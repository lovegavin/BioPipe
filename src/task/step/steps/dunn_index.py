"""Dunn clustering validity index."""
from __future__ import annotations

import numpy as np
from scipy.spatial.distance import pdist

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix
from ._metric_common import label_series


class DunnIndexStep(Step):
    """Ratio of the smallest between-cluster distance to the largest diameter."""

    name = "dunn_index"
    title = "Dunn index"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scipy>=1.10"]
    dependency_imports = ["scipy"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
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
            "feature_dim": {"type": "string", "default": "feature"},
            "label_dim": {"type": "string", "default": "label"},
            "target_label": {"type": "string"},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        feature_form, label_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        X, samples, _ = matrix(feature_form, sample_dim, feature_dim)
        label_samples, labels = label_series(
            label_form, sample_dim, label_dim, ctx.step_params["target_label"], "dunn_index"
        )
        pos = {name: i for i, name in enumerate(label_samples)}
        keep = [i for i, name in enumerate(samples) if name in pos]
        if len(keep) < 4:
            raise StepError("dunn_index: fewer than four shared samples")
        y = [labels[pos[samples[i]]] for i in keep]
        if any(value is None for value in y):
            raise StepError("dunn_index: cluster labels must not be missing")
        classes = sorted(set(y))
        if len(classes) < 2:
            raise StepError("dunn_index: need at least two clusters")
        if min(y.count(cluster) for cluster in classes) < 2:
            raise StepError("dunn_index: each cluster needs at least two samples")

        distances = pdist(X[keep], metric="euclidean")
        matrix_distances = np.zeros((len(keep), len(keep)), dtype=float)
        matrix_distances[np.triu_indices(len(keep), 1)] = distances
        matrix_distances += matrix_distances.T

        diameters = []
        for cluster in classes:
            members = [i for i, value in enumerate(y) if value == cluster]
            diameters.append(float(np.max(matrix_distances[np.ix_(members, members)])))
        max_diameter = max(diameters)
        if max_diameter <= 0:
            raise StepError("dunn_index: a cluster has zero diameter")

        between = []
        for i, first in enumerate(classes):
            for second in classes[i + 1 :]:
                left = [k for k, value in enumerate(y) if value == first]
                right = [k for k, value in enumerate(y) if value == second]
                between.append(float(np.min(matrix_distances[np.ix_(left, right)])))
        score = float(min(between) / max_diameter)

        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[score], [len(keep)], [len(classes)]], dtype=np.float32),
            dims=["metric", "value"],
            labels={
                "metric": {"dunn_index": 0, "n_samples": 1, "n_clusters": 2},
                "value": {"value": 0},
            },
            info={"missing_code": np.nan, "metric": "euclidean"},
        )
        self._export_data = {
            "dunn_index": score,
            "n_samples": len(keep),
            "n_clusters": len(classes),
            "metric": "euclidean",
            "max_diameter": max_diameter,
            "min_between": min(between),
        }
        print(f"[dunn_index] {score:.4f}, k={len(classes)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
