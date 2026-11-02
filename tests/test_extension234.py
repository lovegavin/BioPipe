"""Tests for the embedding linear probe."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.esm_embedding_linear_probe import (
    parse_labels,
    probe_rows,
    resolve_labels,
    validate_input,
)


def _embedding(
    values, labels: list[str] | None = None
) -> Form:
    data = np.asarray(values, dtype=np.float32)
    n_samples, n_features = data.shape
    info: dict = {"missing_code": np.nan}
    if labels is not None:
        info["labels"] = list(labels)
    return Form(
        data=data,
        dims=["sequence", "embedding"],
        labels={
            "sequence": {f"seq{index + 1}": index for index in range(n_samples)},
            "embedding": {f"e{index + 1}": index for index in range(n_features)},
        },
        info=info,
    )


def _separable(samples_per_class: int = 6) -> tuple[np.ndarray, list[str]]:
    rng = np.random.default_rng(7)
    left = rng.normal(0.0, 0.1, size=(samples_per_class, 3))
    right = rng.normal(5.0, 0.1, size=(samples_per_class, 3))
    labels = ["a"] * samples_per_class + ["b"] * samples_per_class
    return np.vstack([left, right]), labels


def test_parse_labels() -> None:
    assert parse_labels("a, b  c") == ["a", "b", "c"]
    assert parse_labels("") == []


def test_resolve_labels_from_information() -> None:
    form = _embedding(np.zeros((3, 2)), labels=["x", "y", "z"])
    assert resolve_labels(form, "sequence", "") == ["x", "y", "z"]
    assert resolve_labels(form, "sequence", "p,q,r") == ["p", "q", "r"]
    with pytest.raises(StepError, match="labels are required"):
        resolve_labels(_embedding(np.zeros((3, 2))), "sequence", "")


def test_probe_separates_the_classes() -> None:
    data, labels = _separable()
    rows, summary = probe_rows(data, labels, folds=3, max_iter=400, random_state=1)
    assert len(rows) == 3
    assert [row[0] for row in rows] == pytest.approx([1.0, 1.0, 1.0])
    assert summary["mean_accuracy"] == pytest.approx(1.0)
    assert summary["std_accuracy"] == pytest.approx(0.0)
    assert summary["baseline_accuracy"] == pytest.approx(0.5)
    assert summary["n_samples"] == 12
    assert summary["n_features"] == 3
    assert summary["n_classes"] == 2
    assert summary["classes"] == ["a", "b"]
    assert sum(row[1] for row in rows) == pytest.approx(12.0)


def test_probe_matches_sklearn_cross_validation() -> None:
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import StratifiedKFold, cross_val_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    data, labels = _separable()
    rows, summary = probe_rows(data, labels, folds=3, max_iter=400, random_state=1)
    model = make_pipeline(
        StandardScaler(), LogisticRegression(max_iter=400, random_state=1)
    )
    splitter = StratifiedKFold(n_splits=3, shuffle=True, random_state=1)
    reference = cross_val_score(
        model, data, np.asarray(labels, dtype=object), cv=splitter
    )
    assert summary["mean_accuracy"] == pytest.approx(float(np.mean(reference)))
    assert [row[0] for row in rows] == pytest.approx(list(reference))


def test_probe_rejects_degenerate_labels() -> None:
    data, labels = _separable(3)
    with pytest.raises(StepError, match="at least two classes"):
        probe_rows(data, ["a"] * 8, folds=2, max_iter=100, random_state=0)
    with pytest.raises(StepError, match="each class needs at least 4 samples"):
        probe_rows(data, labels, folds=4, max_iter=100, random_state=0)


def test_validate_input_errors() -> None:
    data, labels = _separable()
    with pytest.raises(StepError, match="expected a .* embedding form"):
        validate_input(
            Form(
                data=np.zeros((4, 3)),
                dims=["sample", "embedding"],
                labels={"sample": {"s0": 0, "s1": 1, "s2": 2, "s3": 3}, "embedding": {"e0": 0, "e1": 1, "e2": 2}},
                info={"missing_code": np.nan},
            ),
            "sequence",
            "embedding",
            ["a", "b", "a", "b"],
        )
    with pytest.raises(StepError, match="got 3 labels for 12 samples"):
        validate_input(_embedding(data), "sequence", "embedding", ["a", "b", "c"])
    broken = _embedding(data)
    broken.data[0, 0] = np.nan
    with pytest.raises(StepError, match="non-finite values"):
        validate_input(broken, "sequence", "embedding", labels)


def test_runner_round_trip(tmp_path) -> None:
    data, labels = _separable(4)
    ctx = Context(str(tmp_path / "probe"), {"params": {}})
    ctx["embedding"] = _embedding(data)
    run(
        ctx,
        [
            {
                "name": "esm_embedding_linear_probe",
                "inputs": ["embedding"],
                "params": {
                    "labels": ",".join(labels),
                    "cv_folds": 2,
                    "output": "probe",
                },
            }
        ],
    )
    form = ctx["probe"]
    assert form.dims == ["metric", "statistic"]
    assert form.data.shape == (5, 2)
    assert sorted(form.labels["metric"]) == [
        "baseline_accuracy",
        "fold1",
        "fold2",
        "mean_accuracy",
        "std_accuracy",
    ]
    assert set(form.labels["statistic"]) == {"accuracy", "n_test_samples"}
    assert form.data[2, 0] == pytest.approx(1.0)  # mean_accuracy
    assert form.data[4, 0] == pytest.approx(0.5)  # baseline_accuracy
    assert form.info["n_samples"] == 8
    exports = sorted((tmp_path / "probe").rglob("*esm_embedding_linear_probe*.json"))
    assert exports
    assert exports[0].read_text(encoding="utf-8")


def test_runner_validation_errors(tmp_path) -> None:
    data, labels = _separable(4)
    ctx = Context(str(tmp_path / "bad"), {"params": {}})
    ctx["embedding"] = _embedding(data)
    with pytest.raises((StepError, ValueError), match="cv_folds"):
        run(
            ctx,
            [
                {
                    "name": "esm_embedding_linear_probe",
                    "inputs": ["embedding"],
                    "params": {"labels": ",".join(labels), "cv_folds": 1, "output": "probe"},
                }
            ],
        )
