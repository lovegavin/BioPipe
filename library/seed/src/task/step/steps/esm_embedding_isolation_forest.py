"""Isolation-forest novelty scores for an embedding matrix."""

from __future__ import annotations

import numpy as np

from src.core.errors import StepError
from src.core.forms import Form
from src.task.step.base import Step


def novelty_scores(data: np.ndarray, *, n_estimators: int = 100, contamination: float = 0.1, random_state: int = 0) -> tuple[np.ndarray, np.ndarray]:
    """Return decision scores and binary outlier flags."""

    if data.size == 0:
        raise StepError("esm_embedding_isolation_forest: the embedding form is empty")
    if data.shape[0] < 4:
        raise StepError("esm_embedding_isolation_forest: at least four samples are required")
    if not np.isfinite(data).all():
        raise StepError("esm_embedding_isolation_forest: the embedding matrix contains non-finite values")
    if not 0.0 < contamination <= 0.5:
        raise StepError("esm_embedding_isolation_forest: contamination must be in (0, 0.5]")
    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        raise StepError("esm_embedding_isolation_forest: scikit-learn is required for the isolation forest; install it with 'python -m pip install scikit-learn'") from None
    model = IsolationForest(n_estimators=int(n_estimators), contamination=float(contamination), random_state=int(random_state))
    model.fit(np.asarray(data, dtype=np.float64))
    scores = model.decision_function(np.asarray(data, dtype=np.float64))
    flags = model.predict(np.asarray(data, dtype=np.float64))
    return np.asarray(scores, dtype=np.float64), np.asarray(flags, dtype=np.int64)


class EsmEmbeddingIsolationForestStep(Step):
    provider = "operon-core"
    parameters_file = "esm_embedding_isolation_forest.EsmEmbeddingIsolationForestStep.parameters.json"

    definition = {
        'protocol_revision': '3.7',
        'data_formats': {'inputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}],
         'outputs': [{'logical_type': 'form', 'representations': ['form'], 'metadata': {}}]},
        "protocol_version": 3,
        "id": "esm_embedding_isolation_forest",
        "version": "1.0.0",
        "kind": "operator",
        "title": "Embedding isolation forest",
        "category": "Machine Learning",
        "icon": "ChartScatter",
        "contracts": {
            "version": 1,
            "inputs": [{"version": 1, "numeric": True, "dims": [{"param": "sample_dim"}, {"param": "feature_dim"}], "labels": [], "parallel": [], "ndim": 2}],
            "output": {"mode": "declare", "schema": {"ndim": 2, "numeric": True, "info_open": True, "axis_info_open": False}},
            "outputs": [],
        },
        "resources": {"memory_modes": ["full"], "estimate": "estimate_memory"},
        "inputs_arity": 1,
        "output_parameter": "output",
    }

    def run(self, ctx, inputs):
        params = ctx.step_params
        form = inputs[0]
        sample_dim = params["sample_dim"]
        feature_dim = params["feature_dim"]
        if list(form.dims) != [sample_dim, feature_dim]:
            raise StepError(f"esm_embedding_isolation_forest: expected a [{sample_dim!r}, {feature_dim!r}] embedding form, got {list(form.dims)!r}")
        scores, flags = novelty_scores(np.asarray(form.data, dtype=np.float64), n_estimators=int(params.get("n_estimators", 100)), contamination=float(params.get("contamination", 0.1)), random_state=int(params.get("random_state", 0)))
        data = np.column_stack([scores, flags.astype(np.float64)]).astype(np.float32)
        ctx[params.get("output", "novelty")] = Form(
            data=data,
            dims=["sample", "statistic"],
            labels={"sample": dict(form.labels[sample_dim]), "statistic": {"decision_score": 0, "outlier": 1}},
            info={"missing_code": np.nan, "n_outliers": int(flags.sum()), "n_samples": int(len(scores)), "contamination": float(params.get("contamination", 0.1)), "n_estimators": int(params.get("n_estimators", 100))},
        )
        self._export_data = {"n_outliers": int(flags.sum()), "n_samples": int(len(scores))}

    def export(self, ctx):
        return dict(getattr(self, "_export_data", {}))
