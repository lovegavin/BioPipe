"""Quadratic discriminant analysis classifier."""
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


def _split(y, test_size, rng):
    train, test = [], []
    for cls in sorted(set(y)):
        idx = np.flatnonzero(y == cls)
        rng.shuffle(idx)
        n_test = max(1, int(round(len(idx) * test_size)))
        test.extend(idx[:n_test].tolist())
        train.extend(idx[n_test:].tolist())
    if len(set(y[train])) < 2 or not test:
        raise StepError("qda: stratified split left too few classes")
    return np.array(sorted(train)), np.array(sorted(test))


def _fit(x, y, reg):
    y = np.asarray(y)
    classes = sorted(set(y.tolist()))
    means = np.array([x[y == cls].mean(axis=0) for cls in classes])
    covs = []
    priors = []
    for cls in classes:
        block = x[y == cls] - means[classes.index(cls)]
        cov = block.T @ block / max(1, len(block) - 1)
        cov = cov + reg * np.eye(x.shape[1])
        covs.append(cov)
        priors.append(len(block) / len(x))
    return np.array(classes), means, np.array(covs), np.array(priors)


def _log_posterior(x, means, covs, priors):
    out = np.empty((x.shape[0], len(means)))
    for k, (mean, cov) in enumerate(zip(means, covs)):
        sign, logdet = np.linalg.slogdet(cov)
        if sign <= 0:
            raise StepError("qda: class covariance is singular")
        diff = x - mean
        maha = np.einsum("ij,jk,ik->i", diff, np.linalg.inv(cov), diff)
        out[:, k] = np.log(priors[k]) - 0.5 * logdet - 0.5 * maha
    return out


class QdaStep(Step):
    provider = "operon-core"
    parameters_file = "qda.QdaStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "qda",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Quadratic discriminant analysis",
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
            "Quadratic discriminant analysis with per-class covariance; "
            "reports test predictions, accuracy and confusion matrix."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        features, labels_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        target_label = ctx.step_params["target_label"]
        test_size = float(ctx.step_params.get("test_size", 0.25))
        random_state = int(ctx.step_params.get("random_state", 0))
        reg = float(ctx.step_params.get("reg_param", 0.0))
        out_name = ctx.step_params.get("output", self.name)
        if features.dims[0] != sample_dim or feature_dim not in features.dims:
            raise StepError(
                f"qda: features must be [{sample_dim}, {feature_dim}]"
            )
        if labels_form.dims[0] != sample_dim:
            raise StepError(f"qda: labels must have {sample_dim} first")
        if not (0.0 < test_size < 1.0):
            raise StepError("qda: test_size must be in (0, 1)")
        names = _decode(labels_form, label_dim, target_label)
        sample_labels = features.labels[sample_dim]
        label_samples = labels_form.labels[sample_dim]
        common = [name for name in sample_labels if name in set(label_samples)]
        if len(common) < 8:
            raise StepError(f"qda: only {len(common)} shared samples")
        x = np.asarray(features.data, dtype=np.float64)
        row_of = {name: i for i, name in enumerate(sample_labels)}
        label_row = {name: i for i, name in enumerate(label_samples)}
        x = x[[row_of[name] for name in common], :]
        y = [names[label_row[name]] for name in common]
        keep = np.all(np.isfinite(x), axis=1) & np.array(
            [v is not None for v in y], dtype=bool
        )
        x = x[keep]
        y = np.array([v for v, k in zip(y, keep) if k])
        means_all = np.nanmean(x, axis=0)
        x = np.where(np.isfinite(x), x, means_all)
        rng = np.random.default_rng(random_state)
        train, test = _split(y, test_size, rng)
        if len(set(y[train])) < 2:
            raise StepError("qda: training split has < 2 classes")
        classes, means, covs, priors = _fit(x[train], y[train], reg)
        logp = _log_posterior(x[test], means, covs, priors)
        pred = logp.argmax(axis=1)
        class_list = [str(v) for v in classes]
        true_idx = np.array([class_list.index(v) for v in y[test]])
        correct = pred == true_idx
        accuracy = float(correct.mean())
        confusion = np.zeros((len(classes), len(classes)), dtype=int)
        for t, p in zip(true_idx, pred):
            confusion[int(t), int(p)] += 1
        rows = len(test)
        cols = ["true", "predicted", "correct"]
        data = np.column_stack([
            true_idx.astype(np.float32), pred.astype(np.float32),
            correct.astype(np.float32),
        ])
        ctx[out_name] = Form(
            data=data,
            dims=[sample_dim, "statistic"],
            labels={sample_dim: {str(common[int(i)]): k
                                 for k, i in enumerate(test)},
                    "statistic": {name: i for i, name in enumerate(cols)}},
            info={"missing_code": np.nan, "classes": list(map(str, classes)),
                  "test_accuracy": accuracy,
                  "confusion_matrix": confusion.tolist(),
                  "n_train": int(len(train)), "n_test": int(rows),
                  "reg_param": reg},
        )
        self._export_data = {
            "classes": list(map(str, classes)),
            "test_accuracy": accuracy,
            "confusion_matrix": confusion.tolist(),
            "n_train": int(len(train)),
            "n_test": int(rows),
        }
        print(f"[{self.name}] test_accuracy={accuracy:.3f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
