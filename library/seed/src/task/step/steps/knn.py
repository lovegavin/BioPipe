"""k-nearest-neighbour classifier."""
from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step


def _decode_labels(labels_form, label_dim, target_label):
    column = labels_form.labels[label_dim][target_label]
    axis = labels_form.dims.index(label_dim)
    raw = np.asarray(np.take(labels_form.data, [column], axis=axis)).reshape(
        labels_form.data.shape[0]
    )
    enc = labels_form.info.get("encoders", {}).get(label_dim, {})
    target_enc = enc.get(target_label)
    out = []
    for value in raw:
        if not np.isfinite(float(value)):
            out.append(None)
        elif target_enc is not None:
            label = target_enc.inverse.get(int(round(float(value))))
            out.append(str(label) if label is not None else None)
        else:
            out.append(str(int(round(float(value)))))
    return out


def _knn_predict(x_train, y_train, x_test, k, weights):
    classes = sorted(set(np.asarray(y_train).tolist()))
    codes = np.array([classes.index(v) for v in y_train])
    predicted = []
    for point in x_test:
        dist = np.sqrt(np.sum((x_train - point) ** 2, axis=1))
        order = np.argsort(dist, kind="stable")[:k]
        if weights == "uniform":
            weight = np.ones(len(order))
        else:
            weight = 1.0 / (dist[order] + 1e-12)
        score = np.zeros(len(classes))
        for pos, w in zip(order, weight):
            score[codes[pos]] += w
        predicted.append(classes[int(np.argmax(score))])
    return predicted


class KnnStep(Step):
    provider = "operon-core"
    parameters_file = "knn.KnnStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}},
                    {'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "knn",
        "version": "1.0.0",
        "kind": "operator",
        "title": "k nearest neighbours classifier",
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
            "k nearest neighbours classifier with uniform or distance "
            "weights; reports test predictions and accuracy."
        ),
    }

    def run(self, ctx: Context, inputs) -> None:
        features, labels_form = inputs
        sample_dim = ctx.step_params.get("sample_dim", "sample")
        feature_dim = ctx.step_params.get("feature_dim", "feature")
        label_dim = ctx.step_params.get("label_dim", "label")
        target_label = ctx.step_params["target_label"]
        k = int(ctx.step_params.get("n_neighbors", 5))
        weights = ctx.step_params.get("weights", "uniform")
        test_size = float(ctx.step_params.get("test_size", 0.25))
        random_state = int(ctx.step_params.get("random_state", 0))
        out_name = ctx.step_params.get("output", self.name)
        if features.dims[0] != sample_dim or feature_dim not in features.dims:
            raise StepError(
                f"knn: features must be [{sample_dim}, {feature_dim}]"
            )
        if labels_form.dims[0] != sample_dim:
            raise StepError(f"knn: labels must have {sample_dim} first")
        if k < 1:
            raise StepError("knn: n_neighbors must be >= 1")
        if weights not in ("uniform", "distance"):
            raise StepError("knn: weights must be 'uniform' or 'distance'")
        if not (0.0 < test_size < 1.0):
            raise StepError("knn: test_size must be in (0, 1)")
        names = _decode_labels(labels_form, label_dim, target_label)
        sample_labels = features.labels[sample_dim]
        label_samples = labels_form.labels[sample_dim]
        common = [name for name in sample_labels if name in set(label_samples)]
        if len(common) < 8:
            raise StepError(f"knn: only {len(common)} shared samples")
        row_of = {name: i for i, name in enumerate(sample_labels)}
        label_row = {name: i for i, name in enumerate(label_samples)}
        x = np.asarray(features.data, dtype=np.float64)[
            [row_of[name] for name in common], :
        ]
        labels = [names[label_row[name]] for name in common]
        keep = np.all(np.isfinite(x), axis=1) & np.array(
            [v is not None for v in labels], dtype=bool
        )
        x = x[keep]
        labels = np.array([v for v, kk in zip(labels, keep) if kk])
        if len(set(labels.tolist())) < 2:
            raise StepError("knn: need at least two classes")
        rng = np.random.default_rng(random_state)
        train, test = [], []
        for cls in sorted(set(labels.tolist())):
            idx = np.flatnonzero(labels == cls)
            rng.shuffle(idx)
            n_test = max(1, int(round(len(idx) * test_size)))
            test.extend(idx[:n_test].tolist())
            train.extend(idx[n_test:].tolist())
        train = np.array(sorted(train))
        test = np.array(sorted(test))
        if len(train) < k:
            raise StepError(f"knn: only {len(train)} training samples for k={k}")
        classes = sorted(set(labels[train].tolist()))
        predicted_names = _knn_predict(
            x[train], labels[train], x[test], k, weights
        )
        predicted = np.array(
            [classes.index(v) for v in predicted_names], dtype=int
        )
        index = np.array([classes.index(v) for v in labels[test]])
        correct = predicted == index
        accuracy = float(correct.mean())
        confusion = np.zeros((len(classes), len(classes)), dtype=int)
        for t, p in zip(index, predicted):
            confusion[int(t), int(p)] += 1
        ctx[out_name] = Form(
            data=np.column_stack([
                index.astype(np.float32), predicted.astype(np.float32),
                correct.astype(np.float32),
            ]),
            dims=[sample_dim, "statistic"],
            labels={sample_dim: {str(common[int(i)]): pos
                                 for pos, i in enumerate(test)},
                    "statistic": {"true": 0, "predicted": 1,
                                  "correct": 2}},
            info={"missing_code": np.nan, "classes": list(map(str, classes)),
                  "test_accuracy": accuracy,
                  "confusion_matrix": confusion.tolist(),
                  "n_train": int(len(train)), "n_test": int(len(test)),
                  "n_neighbors": k, "weights": weights},
        )
        self._export_data = {
            "classes": list(map(str, classes)),
            "test_accuracy": accuracy,
            "confusion_matrix": confusion.tolist(),
            "n_train": int(len(train)),
            "n_test": int(len(test)),
            "n_neighbors": k,
        }
        print(f"[{self.name}] test_accuracy={accuracy:.3f}")

    def export(self, ctx: Context) -> dict:
        return self._export_data
