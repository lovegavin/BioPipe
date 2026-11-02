"""Tests for the ESM embedding MLP probe."""

from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_mlp_probe import (
    mlp_rows,
    parse_labels,
    resolve_labels,
    validate_input,
)

pytest.importorskip("sklearn")

COLUMNS = ["x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element"]


def _embedding(rows):
    return Form(
        data=np.asarray(rows, dtype=np.float32),
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"seq{index + 1}": index for index in range(len(rows))},
            "embedding": {f"e{index}": index for index in range(len(rows[0]))},
        },
    )


def _separable(per_class=6, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    labels = []
    for value, center in ((0.0, 0.0), (1.0, 6.0)):
        block = rng.normal(loc=center, scale=0.4, size=(per_class, 3))
        rows.extend(block.tolist())
        labels.extend([f"class{int(value)}"] * per_class)
    return _embedding(rows), labels


def _params(**overrides):
    params = {
        "sample_dim": "sequence",
        "feature_dim": "embedding",
        "labels": "",
        "cv_folds": 3,
        "hidden": 8,
        "alpha": 0.0005,
        "max_iter": 300,
        "random_state": 3,
        "output": "probe",
    }
    params.update(overrides)
    return params


def _ctx(tmp_path, name, params):
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx.step_params = dict(params)
    return ctx


def test_parse_and_resolve_labels():
    assert parse_labels("a, b; c  d") == ["a", "b", "c", "d"]
    assert parse_labels("") == []
    form, labels = _separable(3)
    form.info["labels"] = labels
    assert resolve_labels(form, "sequence", "") == labels
    assert resolve_labels(form, "sequence", "x,y") == ["x", "y"]
    with pytest.raises(StepError, match="labels are required"):
        resolve_labels(_separable(3)[0], "sequence", "")


def test_validate_input_rejects_bad_tables():
    form, labels = _separable(3)
    data = validate_input(form, "sequence", "embedding", labels)
    assert data.shape == (6, 3)
    with pytest.raises(StepError, match="expected a"):
        validate_input(form, "sequence", "other", labels)
    with pytest.raises(StepError, match="got 2 labels"):
        validate_input(form, "sequence", "embedding", labels[:2])
    with pytest.raises(StepError, match="at least 4 samples"):
        validate_input(_embedding([[1.0, 2.0], [3.0, 4.0]]), "sequence", "embedding", ["a", "b"])
    broken = _embedding([[1.0, 2.0], [3.0, 4.0], [5.0, 6.0], [7.0, np.nan]])
    with pytest.raises(StepError, match="non-finite"):
        validate_input(broken, "sequence", "embedding", ["a", "b", "c", "d"])


def test_mlp_rows_matches_sklearn_and_summarises():
    from sklearn.model_selection import StratifiedKFold
    from sklearn.neural_network import MLPClassifier
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    form, labels = _separable(6)
    data = np.asarray(form.data, dtype=np.float64)
    rows, summary = mlp_rows(data, labels, folds=3, hidden=8, alpha=0.0005,
                             max_iter=300, random_state=3)
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=3)
    expected = []
    for train, test in splitter.split(data, np.asarray(labels)):
        model = make_pipeline(
            StandardScaler(),
            MLPClassifier(hidden_layer_sizes=(8,), alpha=0.0005, max_iter=300,
                          random_state=3),
        )
        model.fit(data[train], np.asarray(labels)[train])
        expected.append(float(np.mean(model.predict(data[test]) == np.asarray(labels)[test])))
    assert [row[0] for row in rows] == pytest.approx(expected)
    assert summary["mean_accuracy"] == pytest.approx(float(np.mean(expected)))
    assert summary["baseline_accuracy"] == pytest.approx(0.5)
    assert summary["hidden"] == 8
    assert summary["classes"] == ["class0", "class1"]

    with pytest.raises(StepError, match="two classes"):
        mlp_rows(data, ["only"] * len(labels), folds=2)
    with pytest.raises(StepError, match="each class needs at least 4 samples"):
        mlp_rows(data, labels, folds=4)


def test_run_writes_probe_table(tmp_path):
    form, labels = _separable(6)
    form.info["labels"] = labels
    ctx = _ctx(tmp_path, "probe", _params())
    ctx["embedding"] = form
    run(ctx, [{"name": "esm_embedding_mlp_probe", "inputs": ["embedding"],
               "params": dict(ctx.step_params)}])
    output = ctx["probe"]
    assert list(output.dims) == ["metric", "statistic"]
    assert output.data.shape == (6, 2)
    assert output.labels["metric"]["fold1"] == 0
    assert output.labels["metric"]["baseline_accuracy"] == 5
    assert output.info["n_samples"] == 12
    assert output.info["classes"] == ["class0", "class1"]
    assert output.info["mean_accuracy"] >= 0.8


def test_run_validation_errors(tmp_path):
    form, labels = _separable(6)
    form.info["labels"] = labels
    ctx = _ctx(tmp_path, "probe", _params(cv_folds=1))
    ctx["embedding"] = form
    with pytest.raises((StepError, ValueError), match="cv_folds|minimum"):
        run(ctx, [{"name": "esm_embedding_mlp_probe", "inputs": ["embedding"],
                   "params": dict(ctx.step_params)}])

    ctx = _ctx(tmp_path, "probe", _params(hidden=1024))
    ctx["embedding"] = form
    with pytest.raises((StepError, ValueError), match="hidden|maximum"):
        run(ctx, [{"name": "esm_embedding_mlp_probe", "inputs": ["embedding"],
                   "params": dict(ctx.step_params)}])
