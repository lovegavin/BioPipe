"""Binary classification metrics from labels and a score column."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.core.contracts import param, port
from src.task.context import Context
from src.task.step.base import Step


class ClassificationMetricsStep(Step):
    """ROC AUC, PR AUC, accuracy, F1 and MCC for binary labels."""

    name = "classification_metrics"
    title = "Classification metrics"
    category = "Analysis"
    builtin_package = "biopipe-core"
    dependencies = ["scikit-learn>=1.5"]
    dependency_imports = ["sklearn"]
    inputs_arity = 2
    outputs = []
    output_parameter = "output"
    input_contracts = [
        port(ndim=2, dims=[param("sample_dim", "sample"), param("label_dim", "label")]),
        port(ndim=2, dims=[param("sample_dim", "sample"), param("score_dim", "score")]),
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
            "score_dim": {"type": "string", "default": "score"},
            "target_label": {"type": "string"},
            "score_label": {"type": "string"},
            "positive_label": {"type": "string"},
            "threshold": {"type": "number", "minimum": 0.0, "maximum": 1.0, "default": 0.5},
            "output": {"type": "string"},
        },
        "required": ["target_label"],
        "additionalProperties": False,
    }

    def run(self, ctx: Context, inputs) -> None:
        from sklearn.metrics import (
            accuracy_score,
            average_precision_score,
            f1_score,
            matthews_corrcoef,
            roc_auc_score,
        )

        labels_form, score_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        label_dim = ctx.step_params.get("label_dim", "label")
        score_dim = ctx.step_params.get("score_dim", "score")
        target_label = ctx.step_params["target_label"]
        score_label = ctx.step_params.get("score_label")
        threshold = float(ctx.step_params.get("threshold", 0.5))
        if labels_form.data.ndim != 2 or score_form.data.ndim != 2:
            raise StepError("classification_metrics: both inputs must be 2D")
        if sample_dim not in labels_form.dims or sample_dim not in score_form.dims:
            raise StepError("classification_metrics: sample_dim missing from an input")
        if label_dim not in labels_form.dims:
            raise StepError("classification_metrics: label_dim missing")
        if target_label not in labels_form.labels[label_dim]:
            raise StepError("classification_metrics: target_label missing")
        if score_dim not in score_form.dims:
            raise StepError("classification_metrics: score_dim missing")
        score_labels = score_form.labels[score_dim]
        if score_label is None:
            if len(score_labels) != 1:
                raise StepError("classification_metrics: score_label is required for a multi-column score form")
            score_label = next(iter(score_labels))
        if score_label not in score_labels:
            raise StepError("classification_metrics: score_label missing")

        label_samples = labels_form.labels[sample_dim]
        score_samples = score_form.labels[sample_dim]
        common = [name for name in label_samples if name in score_samples]
        if len(common) < 4:
            raise StepError("classification_metrics: fewer than four shared samples")
        sample_axis = labels_form.dims.index(sample_dim)
        label_data = np.asarray(labels_form.data)
        label_col = labels_form.labels[label_dim][target_label]
        if sample_axis != 0:
            label_data = label_data.T
        y_raw = label_data[
            [label_samples[name] for name in common],
            label_col,
        ]
        y_raw = np.asarray(y_raw).reshape(len(common))
        enc = labels_form.info.get("encoders", {}).get(label_dim, {}).get(target_label)
        if enc is not None:
            y_labels = [enc.inverse.get(int(round(float(v))), None) if np.isfinite(v) else None for v in y_raw]
        else:
            y_labels = [str(int(round(float(v)))) if np.isfinite(v) else None for v in y_raw]
        score_sample_axis = score_form.dims.index(sample_dim)
        score_data = np.asarray(score_form.data)
        score_col = score_labels[score_label]
        if score_sample_axis != 0:
            score_data = score_data.T
        scores = score_data[
            [score_samples[name] for name in common],
            score_col,
        ]
        scores = np.asarray(scores, dtype=np.float64).reshape(len(common))
        keep = np.array([label is not None and np.isfinite(score) for label, score in zip(y_labels, scores)])
        y_labels = [label for label, flag in zip(y_labels, keep) if flag]
        scores = scores[keep]
        classes = sorted(set(y_labels))
        if len(classes) != 2:
            raise StepError(f"classification_metrics: need exactly two classes, got {classes}")
        positive = ctx.step_params.get("positive_label", classes[-1])
        if positive not in classes:
            raise StepError(f"classification_metrics: positive_label {positive!r} not in {classes}")
        y_true = np.array([1 if label == positive else 0 for label in y_labels], dtype=np.int64)
        y_pred = (scores >= threshold).astype(np.int64)
        rows = [
            ("ROCAUC", float(roc_auc_score(y_true, scores))),
            ("PRAUC", float(average_precision_score(y_true, scores))),
            ("accuracy", float(accuracy_score(y_true, y_pred))),
            ("F1", float(f1_score(y_true, y_pred, zero_division=0))),
            ("MCC", float(matthews_corrcoef(y_true, y_pred))),
            ("n", float(len(y_true))),
        ]
        ctx[ctx.step_params.get("output", self.name)] = Form(
            data=np.asarray([[value] for _, value in rows], dtype=np.float32),
            dims=["metric", "value"],
            labels={
                "metric": {name: i for i, (name, _) in enumerate(rows)},
                "value": {"value": 0},
            },
            info={"missing_code": np.nan},
        )
        self._export_data = {
            "n_samples": int(len(y_true)),
            "positive_label": positive,
            "classes": classes,
            "threshold": threshold,
        }
        print(f"[classification_metrics] n={len(y_true)} ROCAUC={rows[0][1]:.3f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
