"""Silhouette score for a labelled feature matrix."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step
from ._matrix_common import matrix


def _target_labels(form, sample_dim: str, label_dim: str, target: str):
    if form.data.ndim != 2 or sample_dim not in form.dims or label_dim not in form.dims:
        raise StepError(f"silhouette: labels must have dims [{sample_dim!r}, {label_dim!r}], got {form.dims}")
    columns = form.labels.get(label_dim, {})
    if target not in columns:
        raise StepError(f"silhouette: target_label {target!r} not in {sorted(columns)}")
    axis = form.dims.index(label_dim)
    sample_labels = form.labels[sample_dim]
    values = np.take(form.data, list(range(len(sample_labels))), axis=0)
    values = np.take(values, columns[target], axis=axis).reshape(len(sample_labels))
    encoder = form.info.get("encoders", {}).get(label_dim, {}).get(target)
    labels = []
    for value in values:
        if not np.isfinite(value):
            labels.append(None)
            continue
        if encoder is not None:
            label = encoder.inverse.get(int(round(float(value))))
            labels.append(str(label) if label is not None else None)
        else:
            labels.append(str(int(round(float(value)))))
    return sample_labels, labels


class SilhouetteStep(Step):
    name = "silhouette"
    title = "Silhouette score"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("feature_dim", "feature")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
    ]
    output_contract = {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": True}}
    parameters_schema = {
        "type": "object",
        "properties": {
            "sample_dim": {"type": "string", "default": "sample"},
            "feature_dim": {"type": "string", "default": "feature"},
            "label_dim": {"type": "string", "default": "label"},
            "target_label": {"type": "string"},
            "metric": {"type": "string", "default": "euclidean"},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        try:
            from sklearn.metrics import silhouette_score
        except ImportError as exc:
            raise StepError("silhouette: scikit-learn is required") from exc
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        x, samples, _ = matrix(inputs[0], sample_dim, feature_dim)
        label_samples, labels = _target_labels(inputs[1], sample_dim, label_dim, ctx.step_params["target_label"])
        sample_pos = {name: i for i, name in enumerate(samples)}
        label_pos = {name: i for i, name in enumerate(label_samples)}
        common = [name for name in samples if name in label_pos and labels[label_pos[name]] is not None]
        if len(common) < 3:
            raise StepError(f"silhouette: need at least 3 labelled samples, got {len(common)}")
        y = np.array([labels[label_pos[name]] for name in common])
        if len(set(y)) < 2 or len(set(y)) >= len(y):
            raise StepError(f"silhouette: need 2..n-1 classes, got {len(set(y))}")
        x = x[[sample_pos[name] for name in common]]
        score = float(silhouette_score(x, y, metric=ctx.step_params.get("metric", "euclidean")))
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.array([[score]], dtype=np.float32), dims=["statistic", "value"],
            labels={"statistic": {"silhouette": 0}, "value": {"score": 0}},
            info={"metric": ctx.step_params.get("metric", "euclidean"), "n_samples": len(common), "n_classes": len(set(y))},
        )
        self._export = {"n_samples": len(common), "n_classes": len(set(y)), "silhouette": score}
        print(f"[{self.name}] {self._export}")

    def export(self, ctx: Context) -> dict:
        return self._export
