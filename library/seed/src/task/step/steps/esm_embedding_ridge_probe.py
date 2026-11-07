"""Cross-validated ridge regression on embedding vectors."""

from __future__ import annotations

import numpy as np

from src.core import Form, StepError
from src.task.context import Context
from src.task.step.base import Step

_STATISTICS = ("r2", "rmse", "mae")


def parse_targets(text: str, operator: str = "esm_embedding_ridge_probe") -> np.ndarray:
    """Parse comma, semicolon or whitespace separated target values."""

    tokens = str(text or "").replace(",", " ").replace(";", " ").split()
    if not tokens:
        raise StepError(f"{operator}: targets is required")
    values = []
    for token in tokens:
        try:
            values.append(float(token))
        except ValueError as error:
            raise StepError(f"{operator}: target '{token}' is not a number") from error
    return np.asarray(values, dtype=np.float64)


def resolve_targets(
    form: Form,
    sample_dim: str,
    text: str,
    operator: str = "esm_embedding_ridge_probe",
) -> np.ndarray:
    """Use the ``targets`` parameter, falling back to ``info["targets"]``."""

    raw = str(text or "").strip()
    if raw:
        return parse_targets(raw, operator)
    stored = form.info.get("targets") if isinstance(form.info, dict) else None
    if stored is None:
        raise StepError(
            f"{operator}: targets are required; pass a comma-separated targets "
            "parameter or store them in info['targets']"
        )
    values = np.asarray(stored, dtype=np.float64).reshape(-1)
    if values.size == 0:
        raise StepError(f"{operator}: the targets stored in info['targets'] are empty")
    return values


def validate_input(
    form: Form,
    sample_dim: str,
    feature_dim: str,
    targets: np.ndarray,
    operator: str = "esm_embedding_ridge_probe",
) -> np.ndarray:
    dims = list(form.dims)
    if dims != [sample_dim, feature_dim]:
        raise StepError(
            f"{operator}: expected a [{sample_dim}, {feature_dim}] embedding form, got {dims}"
        )
    data = np.asarray(form.data, dtype=np.float64)
    if data.size == 0:
        raise StepError(f"{operator}: the embedding form is empty")
    if data.shape[1] == 0:
        raise StepError(f"{operator}: the embedding form carries no feature")
    if targets.size != data.shape[0]:
        raise StepError(
            f"{operator}: got {targets.size} targets for {data.shape[0]} samples"
        )
    if not np.all(np.isfinite(data)):
        raise StepError(f"{operator}: the embedding matrix contains non-finite values")
    if not np.all(np.isfinite(targets)):
        raise StepError(f"{operator}: the targets contain non-finite values")
    return data


def _standardize(train: np.ndarray, test: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    mean = train.mean(axis=0)
    scale = train.std(axis=0)
    scale[scale == 0.0] = 1.0
    return (train - mean) / scale, (test - mean) / scale


def ridge_predict(
    train_x: np.ndarray,
    train_y: np.ndarray,
    test_x: np.ndarray,
    *,
    alpha: float,
    standardize: bool = True,
) -> np.ndarray:
    """Fit ridge regression in closed form and predict the held-out samples."""

    if alpha <= 0:
        raise StepError("esm_embedding_ridge_probe: alpha must be positive")
    x_train = np.asarray(train_x, dtype=np.float64)
    y_train = np.asarray(train_y, dtype=np.float64).reshape(-1)
    x_test = np.asarray(test_x, dtype=np.float64)
    if standardize:
        x_train, x_test = _standardize(x_train, x_test)
    x_mean = x_train.mean(axis=0)
    y_mean = float(y_train.mean())
    centred = x_train - x_mean
    gram = centred.T @ centred + alpha * np.eye(centred.shape[1])
    weights = np.linalg.solve(gram, centred.T @ (y_train - y_mean))
    return (x_test - x_mean) @ weights + y_mean


def probe_rows(
    data: np.ndarray,
    targets: np.ndarray,
    *,
    folds: int,
    alpha: float = 1.0,
    standardize: bool = True,
    random_state: int = 0,
) -> tuple[list[dict], dict]:
    """Run k-fold cross-validated ridge regression and summarise the fits."""

    n_samples = data.shape[0]
    if n_samples < 4:
        raise StepError(
            "esm_embedding_ridge_probe: at least four samples are required for cross-validation"
        )
    if folds < 2 or folds > n_samples:
        raise StepError(
            f"esm_embedding_ridge_probe: cv_folds must be between 2 and {n_samples}"
        )
    rng = np.random.default_rng(random_state)
    order = rng.permutation(n_samples)
    fold_slices = np.array_split(order, folds)
    rows: list[dict] = []
    for index, test_index in enumerate(fold_slices):
        train_index = np.setdiff1d(order, test_index)
        predictions = ridge_predict(
            data[train_index],
            targets[train_index],
            data[test_index],
            alpha=alpha,
            standardize=standardize,
        )
        truth = targets[test_index]
        residual = truth - predictions
        ss_res = float(np.sum(residual**2))
        ss_tot = float(np.sum((truth - truth.mean()) ** 2))
        r2 = float("nan") if ss_tot == 0.0 else 1.0 - ss_res / ss_tot
        rmse = float(np.sqrt(np.mean(residual**2)))
        mae = float(np.mean(np.abs(residual)))
        baseline = float(np.sqrt(np.mean((truth - targets[train_index].mean()) ** 2)))
        rows.append(
            {
                "fold": index + 1,
                "r2": r2,
                "rmse": rmse,
                "mae": mae,
                "baseline_rmse": baseline,
                "n_test": int(len(test_index)),
            }
        )
    finite_r2 = [row["r2"] for row in rows if np.isfinite(row["r2"])]
    summary = {
        "n_samples": int(n_samples),
        "n_features": int(data.shape[1]),
        "folds": int(folds),
        "alpha": float(alpha),
        "standardize": bool(standardize),
        "mean_r2": float(np.mean(finite_r2)) if finite_r2 else float("nan"),
        "std_r2": float(np.std(finite_r2)) if finite_r2 else float("nan"),
        "mean_rmse": float(np.mean([row["rmse"] for row in rows])),
        "mean_mae": float(np.mean([row["mae"] for row in rows])),
        "baseline_rmse": float(np.mean([row["baseline_rmse"] for row in rows])),
        "target_mean": float(targets.mean()),
        "target_std": float(targets.std()),
    }
    return rows, summary


class EsmEmbeddingRidgeProbeStep(Step):
    """Predict a continuous property from ESM embeddings with ridge regression."""

    provider = "operon-core"
    parameters_file = "esm_embedding_ridge_probe.EsmEmbeddingRidgeProbeStep.parameters.json"
    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_ridge_probe",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding ridge regression probe",
        "description": (
            "Fit a cross-validated ridge regression from per-sequence embedding "
            "vectors to a continuous property (for example a fitness or stability "
            "measurement) and report per-fold R2, RMSE and MAE with a mean baseline."
        ),
        "category": "Machine Learning",
        "icon": "ChartLine",
        "contracts": {
            "version": 1,
            "inputs": [
                {
                    "version": 1,
                    "numeric": True,
                    "dims": [{"param": "sample_dim"}, {"param": "feature_dim"}],
                    "labels": [],
                    "parallel": [],
                    "ndim": 2,
                    "info": {
                        "representation": {"type": "string", "optional": True},
                        "labels": {"type": "array", "optional": True},
                    },
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
        "dependencies": ["numpy>=1.24"],
        "dependency_imports": [],
        "inputs_arity": 1,
        "outputs": [],
        "output_parameter": "output",
    }

    def run(self, ctx: Context, inputs) -> None:
        params = ctx.step_params
        sample_dim = str(params.get("sample_dim", "sequence")) or "sequence"
        feature_dim = str(params.get("feature_dim", "embedding")) or "embedding"
        metric_dim = str(params.get("metric_dim", "metric")) or "metric"
        out_name = str(params.get("output", "probe")) or "probe"
        form = inputs[0]
        targets = resolve_targets(form, sample_dim, str(params.get("targets", "")))
        data = validate_input(form, sample_dim, feature_dim, targets)
        folds = int(params.get("cv_folds", 5))
        alpha = float(params.get("alpha", 1.0))
        rows, summary = probe_rows(
            data,
            targets,
            folds=folds,
            alpha=alpha,
            standardize=bool(params.get("standardize", True)),
            random_state=int(params.get("random_state", 0)),
        )
        labels = {}
        values: list[tuple[float, float, float]] = []
        for row in rows:
            labels[f"fold{row['fold']}"] = len(labels)
            values.append((row["r2"], row["rmse"], row["mae"]))
        labels["mean_r2"] = len(labels)
        values.append((summary["mean_r2"], float("nan"), float("nan")))
        labels["std_r2"] = len(labels)
        values.append((summary["std_r2"], float("nan"), float("nan")))
        labels["mean_rmse"] = len(labels)
        values.append((float("nan"), summary["mean_rmse"], summary["mean_mae"]))
        labels["baseline_rmse"] = len(labels)
        values.append((float("nan"), summary["baseline_rmse"], float("nan")))
        ctx[out_name] = Form(
            data=np.asarray(values, dtype=np.float32),
            dims=[metric_dim, "statistic"],
            labels={
                metric_dim: labels,
                "statistic": {name: index for index, name in enumerate(_STATISTICS)},
            },
            info={
                "missing_code": np.nan,
                "n_samples": summary["n_samples"],
                "n_features": summary["n_features"],
                "folds": summary["folds"],
                "alpha": summary["alpha"],
                "standardize": summary["standardize"],
                "mean_r2": summary["mean_r2"],
                "std_r2": summary["std_r2"],
                "mean_rmse": summary["mean_rmse"],
                "mean_mae": summary["mean_mae"],
                "baseline_rmse": summary["baseline_rmse"],
                "target_mean": summary["target_mean"],
                "target_std": summary["target_std"],
            },
        )
        self._export_data = {
            "n_samples": summary["n_samples"],
            "folds": summary["folds"],
            "alpha": summary["alpha"],
            "mean_r2": summary["mean_r2"],
            "mean_rmse": summary["mean_rmse"],
            "baseline_rmse": summary["baseline_rmse"],
        }

    def export(self, ctx: Context) -> dict:
        return getattr(self, "_export_data", {})
