"""esm_embedding_mlp_probe: embedding classifier probe."""

import numpy as np
import pytest

sklearn = pytest.importorskip("sklearn")

from src.core.forms import Form
from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_mlp_probe import (
    EsmEmbeddingMlpProbeStep,
    mlp_rows,
    parse_labels,
    resolve_labels,
    validate_input,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}
        self.artifacts = {}


def _embedding(per_class=6, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    labels = []
    for index in range(per_class):
        rows.append(rng.normal(0.0, 0.2, 3))
        labels.append("a")
        rows.append(rng.normal(3.0, 0.2, 3))
        labels.append("b")
    data = np.asarray(rows, dtype=np.float32)
    return Form(
        data=data,
        dims=["sequence", "embedding"],
        labels={"sequence": {f"seq{i}": i for i in range(len(rows))}, "embedding": {f"f{i}": i for i in range(3)}},
        info={"missing_code": np.nan},
    ), labels


def test_parse_and_resolve_labels():
    assert parse_labels("a, b;c") == ["a", "b", "c"]
    form, labels = _embedding(3)
    assert resolve_labels(form, "sequence", "x,y,z,w,q") == ["x", "y", "z", "w", "q"]
    with pytest.raises(StepError, match="labels are required"):
        resolve_labels(form, "sequence", "")
    form.info["labels"] = labels
    assert resolve_labels(form, "sequence", "") == labels


def test_validate_input_errors():
    form, labels = _embedding(2)
    with pytest.raises(StepError, match="expected a"):
        validate_input(form, "wrong", "embedding", labels)
    with pytest.raises(StepError, match="got 1 labels for 4 samples"):
        validate_input(form, "sequence", "embedding", ["a"])
    bad = Form(data=np.full((2, 2), np.nan), dims=["sequence", "embedding"], labels={"sequence": {"a": 0, "b": 1}, "embedding": {"f0": 0, "f1": 1}}, info={})
    with pytest.raises(StepError, match="non-finite"):
        validate_input(bad, "sequence", "embedding", ["a", "b"])


def test_mlp_rows_matches_sklearn_and_summarises():
    from sklearn.linear_model import LogisticRegression  # noqa: F401
    from sklearn.model_selection import StratifiedKFold
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    form, labels = _embedding(6)
    rows, summary = mlp_rows(form.data, labels, folds=3, hidden=8, alpha=0.001, max_iter=400, random_state=3)
    assert len(rows) == 3
    expected = []
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=3)
    for train, test in splitter.split(form.data, labels):
        model = make_pipeline(StandardScaler(), MLPClassifier(hidden_layer_sizes=(8,), alpha=0.001, max_iter=400, random_state=3))
        model.fit(form.data[train], [labels[i] for i in train])
        predicted = model.predict(form.data[test])
        expected.append(float(np.mean([predicted[i] == labels[test[i]] for i in range(len(test))])))
    assert [row[0] for row in rows] == pytest.approx(expected)
    assert summary["baseline_accuracy"] == pytest.approx(0.5)
    assert summary["n_samples"] == 12


def test_run_writes_probe_table():
    form, labels = _embedding(6)
    import tempfile
    ctx = Context(tempfile.mkdtemp(), {"params": {}})
    ctx["embeddings"] = form
    run(ctx, [{"name": "esm_embedding_mlp_probe", "inputs": ["embeddings"], "params": {"output": "probe", "labels": ",".join(labels), "sample_dim": "sequence", "feature_dim": "embedding", "cv_folds": 3, "hidden": 8, "max_iter": 400, "random_state": 3}}])
    result = ctx["probe"]
    assert result.dims == ["metric", "statistic"]
    assert result.data.shape[0] == 6
    assert result.info["mean_accuracy"] >= 0.8


def test_validation_errors():
    form, labels = _embedding(2)
    with pytest.raises((StepError, ValueError)):
        mlp_rows(form.data, ["a", "b", "a", "b"], folds=1)
    with pytest.raises((StepError, ValueError)):
        import tempfile
        ctx = Context(tempfile.mkdtemp(), {"params": {}})
        ctx.step_params = {"output": "probe", "labels": "a,b,a,b"}
        ctx["embeddings"] = form
        EsmEmbeddingMlpProbeStep().run(ctx, [form])
