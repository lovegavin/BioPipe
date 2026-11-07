"""Cross-validated logistic-regression probe on protein embeddings.

A linear probe is the standard sanity check for an embedding: if two labelled
groups are separable with a linear model, the representation carries that
signal.  The operator standardises the features, runs stratified k-fold
cross-validation and reports the per-fold accuracy together with the mean, the
standard deviation and the majority-class baseline.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_STATISTICS = ("accuracy", "n_test_samples")
_MAX_FOLDS = 10


def parse_labels(text: str) -> list[str]:
    """Parse a comma or whitespace separated label list."""

    tokens = [token.strip() for token in str(text).replace(",", " ").split()]
    return [token for token in tokens if token]


def resolve_labels(form: Form, sample_dim: str, text: str) -> list[str]:
    """Read labels from the parameter or from the input information."""

    labels = parse_labels(text)
    if not labels:
        stored = form.info.get("labels") if form.info else None
        if stored is not None:
            labels = [str(value) for value in stored]
    if not labels:
        raise StepError(
            "esm_embedding_linear_probe: labels are required; pass a "
            "comma-separated labels parameter or store them in info['labels']"
        )
    return labels


def validate_input(
    form: Form, sample_dim: str, feature_dim: str, labels: list[str]
) -> np.ndarray:
    dims = list(form.dims)
    if dims != [sample_dim, feature_dim]:
        raise StepError(
            "esm_embedding_linear_probe: expected a "
            f"[{sample_dim}, {feature_dim}] embedding form, got {dims}"
        )
    data = np.asarray(form.data, dtype=np.float64)
    if data.ndim != 2 or data.shape[0] == 0 or data.shape[1] == 0:
        raise StepError(
            "esm_embedding_linear_probe: the embedding form is empty"
        )
    if len(labels) != data.shape[0]:
        raise StepError(
            "esm_embedding_linear_probe: got "
            f"{len(labels)} labels for {data.shape[0]} samples"
        )
    if not np.isfinite(data).all():
        raise StepError(
            "esm_embedding_linear_probe: the embedding matrix contains "
            "non-finite values"
        )
    return data


def probe_rows(
    data: np.ndarray,
    labels: list[str],
    *,
    folds: int,
    max_iter: int,
    random_state: int,
) -> tuple[list[tuple[float, float]], dict]:
    """Return per-fold accuracy rows and a summary dictionary."""

    try:
        from sklearn.linear_model import LogisticRegression
        from sklearn.model_selection import StratifiedKFold
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as error:
        raise StepError(
            "esm_embedding_linear_probe: scikit-learn is required for the "
            "logistic-regression probe; install it with "
            "'python -m pip install scikit-learn'"
        ) from error

    values = np.asarray(labels, dtype=object)
    classes, counts = np.unique(values, return_counts=True)
    if len(classes) < 2:
        raise StepError(
            "esm_embedding_linear_probe: the labels must contain at least two "
            "classes"
        )
    if counts.min() < folds:
        raise StepError(
            "esm_embedding_linear_probe: each class needs at least "
            f"{folds} samples for {folds}-fold cross-validation"
        )
    splitter = StratifiedKFold(
        n_splits=folds, shuffle=True, random_state=random_state
    )
    accuracies: list[float] = []
    sizes: list[int] = []
    for train, test in splitter.split(data, values):
        model = make_pipeline(
            StandardScaler(),
            LogisticRegression(max_iter=max_iter, random_state=random_state),
        )
        model.fit(data[train], values[train])
        predicted = model.predict(data[test])
        accuracies.append(float(np.mean(predicted == values[test])))
        sizes.append(int(len(test)))
    majority = float(counts.max() / counts.sum())
    rows = [
        (accuracy, float(size))
        for accuracy, size in zip(accuracies, sizes)
    ]
    summary = {
        "n_samples": int(data.shape[0]),
        "n_features": int(data.shape[1]),
        "n_classes": int(len(classes)),
        "classes": [str(value) for value in classes],
        "folds": folds,
        "mean_accuracy": float(np.mean(accuracies)),
        "std_accuracy": float(np.std(accuracies)),
        "baseline_accuracy": majority,
    }
    return rows, summary


class EsmEmbeddingLinearProbeStep(Step):
    """Stratified logistic-regression probe on a protein embedding form."""

    provider = "operon-core"

    parameters_file = (
        "esm_embedding_linear_probe."
        "EsmEmbeddingLinearProbeStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_linear_probe",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM embedding linear probe",
        "description": (
            "Fit a standardised logistic-regression probe on an embedding "
            "table with stratified k-fold cross-validation and report per-fold "
            "accuracy, the mean and standard deviation, and the "
            "majority-class baseline."
        ),
        "category": "Machine Learning",
        "icon": "Brain",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "info": {
                        "missing_code": {"type": ["number", "null"]},
                        "encoders": {"type": "object", "optional": True},
                    },
                    "dims": [
                        {
                            "param": "sample_dim",
                            "default": "sequence",
                        },
                        {
                            "param": "feature_dim",
                            "default": "embedding",
                        },
                    ],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                }
            ],
            "output": {
                "mode": "declare",
                "schema": {
                    "ndim": 2,
                    "numeric": True,
                    "info_open": True,
                    "axis_info_open": True,
                },
            },
        },
        "resources": {
            "memory_modes": ["full"],
            "supports_cuda": False,
            "estimate": "estimate_memory",
        },
        "dependencies": ["numpy>=1.24", "scikit-learn>=1.3"],
        "dependency_imports": ["sklearn"],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sequence")).strip() or "sequence"
        feature_dim = str(params.get("feature_dim", "embedding")).strip() or "embedding"
        folds = int(params.get("cv_folds") or 5)
        max_iter = int(params.get("max_iter") or 1000)
        random_state = int(params.get("random_state") or 0)
        out_name = params.get("output", self.name)

        if folds < 2 or folds > _MAX_FOLDS:
            raise StepError(
                "esm_embedding_linear_probe: cv_folds must be between 2 and "
                f"{_MAX_FOLDS}"
            )
        if max_iter < 10:
            raise StepError(
                "esm_embedding_linear_probe: max_iter must be at least 10"
            )

        form = inputs[0]
        labels = resolve_labels(form, sample_dim, str(params.get("labels", "")))
        data = validate_input(form, sample_dim, feature_dim, labels)
        rows, summary = probe_rows(
            data,
            labels,
            folds=folds,
            max_iter=max_iter,
            random_state=random_state,
        )

        metric_labels = {
            f"fold{index + 1}": index for index in range(len(rows))
        }
        offset = len(rows)
        for index, name in enumerate(
            ("mean_accuracy", "std_accuracy", "baseline_accuracy")
        ):
            metric_labels[name] = offset + index
        data_out = np.asarray(
            rows
            + [
                (summary["mean_accuracy"], float(summary["n_samples"])),
                (summary["std_accuracy"], float(summary["n_samples"])),
                (summary["baseline_accuracy"], float(summary["n_samples"])),
            ],
            dtype=np.float32,
        )
        form_out = Form(
            data=data_out,
            dims=["metric", "statistic"],
            labels={
                "metric": metric_labels,
                "statistic": {
                    name: index for index, name in enumerate(_STATISTICS)
                },
            },
            info=dict(summary),
        )
        ctx[out_name] = form_out
        self._export_data = {
            "n_samples": summary["n_samples"],
            "n_features": summary["n_features"],
            "n_classes": summary["n_classes"],
            "mean_accuracy": summary["mean_accuracy"],
            "baseline_accuracy": summary["baseline_accuracy"],
        }
        print(
            f"[{self.name}] {summary['n_samples']} samples, "
            f"{summary['n_features']} features -> accuracy "
            f"{summary['mean_accuracy']:.3f} (baseline "
            f"{summary['baseline_accuracy']:.3f})"
        )

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
