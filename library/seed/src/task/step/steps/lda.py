"""Linear discriminant analysis."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def _decode(labels_form, label_dim, target_label):
    column = labels_form.labels[label_dim][target_label]
    axis = labels_form.dims.index(label_dim)
    raw = np.take(labels_form.data, [column], axis=axis)
    raw = np.asarray(raw).reshape(raw.shape[0])
    enc = labels_form.info.get("encoders", {}).get(label_dim, {})
    target_enc = enc.get(target_label)
    names = []
    for value in raw:
        if not np.isfinite(float(value)):
            names.append(None)
            continue
        if target_enc is not None:
            label = target_enc.inverse.get(int(round(float(value))))
            names.append(str(label) if label is not None else None)
        else:
            names.append(str(int(round(float(value)))))
    return names


def _fit(x, y, tol):
    y = np.asarray(y)
    classes = sorted(set(y.tolist()))
    n, p = x.shape
    g = len(classes)
    if g < 2:
        raise StepError("lda: need at least two classes")
    if n - g < 1:
        raise StepError("lda: need more observations than classes")
    counts = np.array([int(np.sum(y == cls)) for cls in classes], dtype=np.float64)
    priors = counts / n
    means = np.array([x[y == cls].mean(axis=0) for cls in classes])
    per_sample = means[[classes.index(v) for v in y]]
    departure = x - per_sample
    f1 = np.sqrt(np.sum(departure ** 2, axis=0) / (n - 1))
    if np.any(f1 < tol):
        raise StepError("lda: a variable is constant within groups")
    scale0 = np.diag(1.0 / f1)
    block = np.sqrt(1.0 / (n - g)) * (departure @ scale0)
    _, singular, vt = np.linalg.svd(block, full_matrices=False)
    rank = int(np.sum(singular > tol))
    if rank == 0:
        raise StepError("lda: discriminant scores are numerically zero")
    scaling = scale0 @ vt[:rank].T @ np.diag(1.0 / singular[:rank])
    xbar = priors @ means
    centered_means = means - xbar
    group_block = (np.sqrt(n * priors / (g - 1))[:, None]
                   * (centered_means @ scaling))
    _, svd, vt2 = np.linalg.svd(group_block, full_matrices=False)
    rank2 = int(np.sum(svd > tol * svd[0]))
    if rank2 == 0:
        raise StepError("lda: group means are numerically identical")
    scaling = scaling @ vt2[:rank2].T
    scores = (x - xbar) @ scaling
    return classes, counts, priors, means, scaling, svd[:rank2], xbar, scores


class LdaStep(Step):
    provider = "operon-core"
    parameters_file = "lda.LdaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "lda",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Linear discriminant analysis",
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "feature_dim", "default": "feature"}],
                 "labels": [], "parallel": []},
                {"version": 1, "numeric": True, "info": {}, "ndim": 2,
                 "dims": [{"param": "sample_dim", "default": "sample"},
                          {"param": "label_dim", "default": "label"}],
                 "labels": [], "parallel": []},
            ],
            "output": {"mode": "declare",
                       "schema": {"ndim": 2, "numeric": True,
                                  "info_open": True,
                                  "axis_info_open": True}},
        },
        "resources": {"memory_modes": ["full"], "supports_cuda": False,
                      "estimate": "estimate_memory"},
        "dependencies": ["numpy>=1.26"],
        "dependency_imports": ["numpy"],
        "inputs_arity": 2,
        "outputs": [],
        "output_parameter": "output",
        "description": (
            "Linear discriminant analysis fit on all labelled samples; "
            "reports fitted classes, posteriors class scores and LD scores."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        features, labels_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        target_label = ctx.step_params["target_label"]
        tol = float(ctx.step_params.get("tol", 1e-4))
        out_name = ctx.step_params.get("output", self.name)
        if features.dims[0] != sample_dim or feature_dim not in features.dims:
            raise StepError(f"lda: features must be [{sample_dim}, {feature_dim}]")
        if labels_form.dims[0] != sample_dim:
            raise StepError(f"lda: labels must have {sample_dim} first")
        names = _decode(labels_form, label_dim, target_label)
        sample_labels = features.labels[sample_dim]
        label_samples = labels_form.labels[sample_dim]
        common = [name for name in sample_labels if name in set(label_samples)]
        if len(common) < 4:
            raise StepError(f"lda: only {len(common)} shared samples")
        x = np.asarray(features.data, dtype=np.float64)
        row_of = {name: i for i, name in enumerate(sample_labels)}
        label_row = {name: i for i, name in enumerate(label_samples)}
        x = x[[row_of[name] for name in common], :]
        y = [names[label_row[name]] for name in common]
        keep = np.all(np.isfinite(x), axis=1) & np.array(
            [v is not None for v in y], dtype=bool)
        x = x[keep]
        y = [v for v, k in zip(y, keep) if k]
        if len(set(y)) < 2:
            raise StepError("lda: need at least two classes")
        classes, counts, priors, means, scaling, svd, xbar, scores = _fit(
            x, y, tol)
        class_list = [str(v) for v in classes]
        true_idx = np.array([class_list.index(v) for v in y])
        dm = (means - xbar) @ scaling
        logpost = scores @ dm.T - 0.5 * np.sum(dm ** 2, axis=1) + np.log(priors)
        logpost = logpost - logpost.max(axis=1, keepdims=True)
        post = np.exp(logpost)
        post = post / post.sum(axis=1, keepdims=True)
        pred = post.argmax(axis=1)
        correct = pred == true_idx
        confusion = np.zeros((len(classes), len(classes)), dtype=int)
        for t, p in zip(true_idx, pred):
            confusion[int(t), int(p)] += 1
        columns = ["true", "predicted", "correct"] + [
            f"LD{i + 1}" for i in range(scores.shape[1])]
        data = np.column_stack([
            true_idx.astype(np.float32),
            pred.astype(np.float32),
            correct.astype(np.float32),
            scores.astype(np.float32),
        ])
        sample_labels_out = {name: i for i, name in enumerate(common)}
        ctx[out_name] = Form(
            data=data,
            dims=[sample_dim, "statistic"],
            labels={sample_dim: sample_labels_out,
                    "statistic": {name: i for i, name in enumerate(columns)}},
            info={"missing_code": np.nan,
                  "classes": class_list,
                  "priors": priors.tolist(),
                  "counts": counts.tolist(),
                  "means": means.tolist(),
                  "scaling": scaling.tolist(),
                  "svd": svd.tolist(),
                  "accuracy": float(correct.mean()),
                  "confusion_matrix": confusion.tolist()},
        )
        self._export_data = {
            "classes": class_list,
            "priors": priors.tolist(),
            "svd": svd.tolist(),
            "accuracy": float(correct.mean()),
            "confusion_matrix": confusion.tolist(),
        }
        print(f"[{self.name}] accuracy={float(correct.mean()):.3f} "
              f"classes={len(classes)}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
