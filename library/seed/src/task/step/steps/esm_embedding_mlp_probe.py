"""Non-linear probe over an ESM embedding table with a scikit-learn MLP.

The linear probe (``esm_embedding_linear_probe``) answers "is the signal
linearly decodable?".  This operator fits a small multi-layer perceptron with
stratified k-fold cross-validation, which shows whether a curved decision
boundary buys anything over the linear baseline.
"""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_MAX_FOLDS = 10
_MIN_SAMPLES = 4


def parse_labels(text: str) -> list[str]:
    """Split a comma, semicolon or whitespace separated label list."""

    tokens = [
        token
        for chunk in str(text or "").replace(",", " ").replace(";", " ").split()
        for token in [chunk.strip()]
        if token
    ]
    return tokens


def resolve_labels(form: Form, sample_dim: str, text: str) -> list[str]:
    """Return explicit labels, falling back to ``info['labels']``."""

    labels = parse_labels(text)
    if labels:
        return labels
    stored = form.info.get("labels")
    if isinstance(stored, (list, tuple)) and stored:
        return [str(value) for value in stored]
    raise StepError(
        "esm_embedding_mlp_probe: labels are required; pass a comma-separated "
        "labels parameter or store them in info['labels']"
    )


def validate_input(
    form: Form, sample_dim: str, feature_dim: str, labels: list[str]
) -> np.ndarray:
    """Validate the embedding table and return a float64 copy."""

    if list(form.dims) != [sample_dim, feature_dim]:
        raise StepError(
            "esm_embedding_mlp_probe: expected a "
            f"[{sample_dim}, {feature_dim}] embedding form, got {list(form.dims)}"
        )
    data = np.asarray(form.data, dtype=np.float64)
    if data.size == 0:
        raise StepError("esm_embedding_mlp_probe: the embedding form is empty")
    if data.shape[0] != len(labels):
        raise StepError(
            f"esm_embedding_mlp_probe: got {len(labels)} labels for "
            f"{data.shape[0]} samples"
        )
    if not np.all(np.isfinite(data)):
        raise StepError(
            "esm_embedding_mlp_probe: the embedding matrix contains non-finite values"
        )
    if data.shape[0] < _MIN_SAMPLES:
        raise StepError(
            f"esm_embedding_mlp_probe: at least {_MIN_SAMPLES} samples are required"
        )
    return data


def mlp_rows(
    data: np.ndarray,
    labels: list[str],
    *,
    folds: int,
    hidden: int = 32,
    alpha: float = 0.001,
    max_iter: int = 600,
    random_state: int = 0,
):
    """Fit an MLPClassifier per fold and return rows plus a summary."""

    try:
        from sklearn.model_selection import StratifiedKFold
        from sklearn.neural_network import MLPClassifier
        from sklearn.pipeline import make_pipeline
        from sklearn.preprocessing import StandardScaler
    except ImportError as error:  # pragma: no cover - dependency guard
        raise StepError(
            "esm_embedding_mlp_probe: scikit-learn is required for the MLP "
            "probe; install it with 'python -m pip install scikit-learn'"
        ) from error

    values = np.asarray(labels, dtype=object)
    classes, counts = np.unique(values, return_counts=True)
    if len(classes) < 2:
        raise StepError(
            "esm_embedding_mlp_probe: the labels must contain at least two classes"
        )
    if counts.min() < folds:
        raise StepError(
            "esm_embedding_mlp_probe: each class needs at least "
            f"{folds} samples for {folds}-fold cross-validation"
        )

    splitter = StratifiedKFold(n_splits=folds, shuffle=True, random_state=random_state)
    accuracies: list[float] = []
    sizes: list[int] = []
    for train, test in splitter.split(data, values):
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(
                hidden_layer_sizes=(int(hidden),),
                alpha=float(alpha),
                max_iter=int(max_iter),
                random_state=int(random_state),
            ),
        )
        model.fit(data[train], values[train])
        predicted = model.predict(data[test])
        accuracies.append(float(np.mean(predicted == values[test])))
        sizes.append(int(len(test)))

    rows = [(accuracy, float(size)) for accuracy, size in zip(accuracies, sizes)]
    summary = {
        "n_samples": int(data.shape[0]),
        "n_features": int(data.shape[1]),
        "n_classes": int(len(classes)),
        "classes": [str(value) for value in classes],
        "folds": int(folds),
        "hidden": int(hidden),
        "alpha": float(alpha),
        "mean_accuracy": float(np.mean(accuracies)),
        "std_accuracy": float(np.std(accuracies)),
        "baseline_accuracy": float(counts.max() / counts.sum()),
    }
    return rows, summary


class EsmEmbeddingMlpProbeStep(Step):
    """Stratified MLP probe on a protein embedding form."""

    provider = "operon-core"
    parameters_file = (
        "esm_embedding_mlp_probe.EsmEmbeddingMlpProbeStep.parameters.json"
    )

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_mlp_probe",
        "version": "1.0.0",
        "kind": "operator",
        "title": "ESM embedding MLP probe",
        "description": (
            "Fit a standardised multi-layer perceptron on an embedding table "
            "with stratified k-fold cross-validation and report per-fold "
            "accuracy, the mean and standard deviation, and the majority-class "
            "baseline against the linear probe."
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
                        {"param": "sample_dim", "default": "sequence"},
                        {"param": "feature_dim", "default": "embedding"},
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
        hidden = int(params.get("hidden") or 32)
        alpha = float(params.get("alpha", 0.001))
        max_iter = int(params.get("max_iter") or 600)
        random_state = int(params.get("random_state") or 0)
        out_name = str(params.get("output", "probe")) or "probe"

        if folds < 2 or folds > _MAX_FOLDS:
            raise StepError(
                "esm_embedding_mlp_probe: cv_folds must be between 2 and "
                f"{_MAX_FOLDS}"
            )
        if hidden < 2 or hidden > 512:
            raise StepError("esm_embedding_mlp_probe: hidden must be between 2 and 512")
        if alpha <= 0:
            raise StepError("esm_embedding_mlp_probe: alpha must be positive")
        if max_iter < 10:
            raise StepError("esm_embedding_mlp_probe: max_iter must be at least 10")

        form = inputs[0]
        labels = resolve_labels(form, sample_dim, str(params.get("labels", "")))
        data = validate_input(form, sample_dim, feature_dim, labels)
        rows, summary = mlp_rows(
            data,
            labels,
            folds=folds,
            hidden=hidden,
            alpha=alpha,
            max_iter=max_iter,
            random_state=random_state,
        )

        metric_labels = {f"fold{index + 1}": index for index in range(len(rows))}
        metric_labels["mean_accuracy"] = len(rows)
        metric_labels["std_accuracy"] = len(rows) + 1
        metric_labels["baseline_accuracy"] = len(rows) + 2
        metric_data = np.zeros((len(metric_labels), 2), dtype=np.float32)
        for index, (accuracy, size) in enumerate(rows):
            metric_data[index] = (accuracy, size)
        metric_data[len(rows)] = (summary["mean_accuracy"], float(len(rows)))
        metric_data[len(rows) + 1] = (summary["std_accuracy"], 0.0)
        metric_data[len(rows) + 2] = (summary["baseline_accuracy"], 0.0)

        ctx[out_name] = Form(
            data=metric_data,
            dims=["metric", "statistic"],
            labels={
                "metric": metric_labels,
                "statistic": {"accuracy": 0, "n_test_samples": 1},
            },
            info={
                "missing_code": np.nan,
                "n_samples": summary["n_samples"],
                "n_features": summary["n_features"],
                "n_classes": summary["n_classes"],
                "classes": summary["classes"],
                "folds": summary["folds"],
                "hidden": summary["hidden"],
                "alpha": summary["alpha"],
                "mean_accuracy": summary["mean_accuracy"],
                "std_accuracy": summary["std_accuracy"],
                "baseline_accuracy": summary["baseline_accuracy"],
            },
        )
        self._export_data = {
            "n_samples": summary["n_samples"],
            "n_features": summary["n_features"],
            "classes": summary["classes"],
            "hidden": summary["hidden"],
            "mean_accuracy": summary["mean_accuracy"],
            "baseline_accuracy": summary["baseline_accuracy"],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
