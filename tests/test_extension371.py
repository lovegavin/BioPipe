"""Contract tests for the model-selection operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.ml_feature_ablation import MlFeatureAblationStep
from src.task.step.steps.ml_logistic_fit import MlLogisticFitStep
from src.task.step.steps.ml_stratified_folds import MlStratifiedFoldsStep
from src.task.step.steps.ml_train_test_split import MlTrainTestSplitStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)


def _run(step, params, inputs):
    merged = dict(params)
    merged["output"] = "out"
    ctx = Ctx(merged)
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    return Form(
        values,
        dims=["sample", "label"],
        labels={"sample": {f"s{i}": i for i in range(values.shape[0])},
                "label": {"label": 0}},
    )


def _features(values):
    values = np.asarray(values, dtype=float)
    return Form(
        values,
        dims=["sample", "feature"],
        labels={"sample": {f"s{i}": i for i in range(values.shape[0])},
                "feature": {f"f{j}": j for j in range(values.shape[1])}},
    )


def test_folds_partition_and_stratify():
    y = [0] * 6 + [1] * 4
    out, summary = _run(
        MlStratifiedFoldsStep(),
        {"n_splits": 2, "shuffle": False, "seed": 0},
        [_labels(y)],
    )
    folds = out.data[:, 0]
    assert summary["fold_sizes"] == [5, 5]
    for fold in (0, 1):
        mask = folds == fold
        assert int(np.sum(mask[:6])) == 3
        assert int(np.sum(mask[6:])) == 2
    assert out.labels["statistic"] == {"fold": 0}


def test_folds_reject_too_many_splits():
    with pytest.raises(StepError, match="n_splits"):
        _run(MlStratifiedFoldsStep(), {"n_splits": 5},
             [_labels([0] * 3 + [1] * 3)])


def test_split_sizes_and_stratification():
    y = [0] * 6 + [1] * 6
    out, summary = _run(
        MlTrainTestSplitStep(),
        {"test_fraction": 0.25, "seed": 0},
        [_labels(y)],
    )
    mask = out.data[:, 0].astype(bool)
    assert summary["n_test"] == 3 and summary["n_train"] == 9
    assert 1 <= int(np.sum(mask[:6])) <= 2
    assert 1 <= int(np.sum(mask[6:])) <= 2


def test_logistic_separable_problem():
    X = np.array([[-2.0], [-1.0], [1.0], [2.0]])
    y = [0, 0, 1, 1]
    out, summary = _run(
        MlLogisticFitStep(),
        {"C": 1.0, "max_iter": 1000},
        [_features(X), _labels(y)],
    )
    assert summary["accuracy"] == 1.0
    assert summary["roc_auc"] == 1.0
    assert out.data[0, 0] > 0
    assert out.data[0, 1] == pytest.approx(np.exp(out.data[0, 0]))


def test_logistic_regularization_shrinks_coefficients():
    rng = np.random.RandomState(0)
    X = rng.normal(size=(40, 3))
    y = (X[:, 0] + 0.3 * rng.normal(size=40) > 0).astype(int)
    strong, _ = _run(MlLogisticFitStep(), {"C": 0.01}, [_features(X), _labels(y)])
    weak, _ = _run(MlLogisticFitStep(), {"C": 10.0}, [_features(X), _labels(y)])
    assert np.abs(strong.data[:, 0]).max() < np.abs(weak.data[:, 0]).max()


def test_ablation_detects_informative_feature():
    X = np.array([[-2.0, 0.0], [-1.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    y = [0, 0, 1, 1]
    out, summary = _run(
        MlFeatureAblationStep(),
        {"metric": "roc_auc"},
        [_features(X), _labels(y)],
    )
    deltas = dict(zip(out.labels["feature"], out.data[:, 0]))
    assert deltas["f0"] == pytest.approx(0.5, abs=1e-8)
    assert deltas["f1"] == pytest.approx(0.0, abs=1e-8)
    assert summary["baseline"] == 1.0


def test_ablation_accuracy_metric():
    X = np.array([[-2.0, 0.0], [-1.0, 0.0], [1.0, 0.0], [2.0, 0.0]])
    out, summary = _run(
        MlFeatureAblationStep(),
        {"metric": "accuracy"},
        [_features(X), _labels([0, 0, 1, 1])],
    )
    assert summary["metric"] == "accuracy"
    assert out.data[0, 0] == pytest.approx(0.5, abs=1e-8)


def test_single_class_rejected():
    with pytest.raises(StepError, match="two classes"):
        _run(MlStratifiedFoldsStep(), {"n_splits": 2}, [_labels([1, 1, 1, 1])])
