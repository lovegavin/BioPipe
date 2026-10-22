"""Standalone verification of the train_classifier operator.

Run with: python tasks/ml_classification_route_demo/test_train_classifier.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.train_classifier import TrainClassifierStep
from biopipe_sdk.testing import run_operator


DATA = Path(__file__).parent / "input"


def _make_features(matrix, sample_labels, feature_labels):
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["sample", "feature"],
        labels={
            "sample": {s: i for i, s in enumerate(sample_labels)},
            "feature": {f: i for i, f in enumerate(feature_labels)},
        },
        info={"missing_code": np.nan},
    )


def _make_labels(values, sample_labels, label_name):
    enc = get_encoder("labelencoder")
    codes = enc.fit_transform(values)
    return Form(
        data=np.array(codes, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(sample_labels)},
            "label": {label_name: 0},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"label": {label_name: enc}},
        },
    )


def test_perfect_separation_hand_counted():
    """Feature A separates the two classes exactly; feature B is noise.

    With logistic regression on centered data, |coef_A| must be
    strictly larger than |coef_B|. The sign of coef_A must be
    consistent: larger A values push toward the second class in
    sorted class order.
    """
    X = np.array([
        [10.0, 0.0], [11.0, 0.5], [12.0, -0.5], [13.0, 0.2],
        [-10.0, 0.0], [-11.0, -0.3], [-12.0, 0.4], [-13.0, 0.1],
    ], dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    features = ["A", "B"]
    labels = ["class0", "class0", "class0", "class0",
              "class1", "class1", "class1", "class1"]
    feat_form = _make_features(X, samples, features)
    label_form = _make_labels(labels, samples, "grp")
    out = run_operator(TrainClassifierStep, [feat_form, label_form], {
        "sample_dim": "sample",
        "feature_dim": "feature",
        "label_dim": "label",
        "target_label": "grp",
        "method": "logistic",
        "test_size": 0.25,
        "cv_folds": 2,
        "random_state": 0,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    signed = out.data[:, stats["signed_score"]]
    a_idx = out.labels["feature"]["A"]
    b_idx = out.labels["feature"]["B"]
    assert imp[a_idx] > imp[b_idx], (imp[a_idx], imp[b_idx])
    assert signed[a_idx] < 0, signed[a_idx]  # larger A -> class1 (index 1)
    assert abs(imp[a_idx] - abs(signed[a_idx])) < 1e-6
    print("  perfect separation hand-counted      ok")


def test_random_forest_importance_non_negative():
    X = np.array([
        [1.0, 5.0], [2.0, 4.0], [3.0, 3.0], [4.0, 2.0],
        [5.0, 1.0], [6.0, 0.5], [7.0, 0.2], [8.0, 0.1],
    ], dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    labels = ["a", "a", "a", "a", "b", "b", "b", "b"]
    feat_form = _make_features(X, samples, ["A", "B"])
    label_form = _make_labels(labels, samples, "grp")
    out = run_operator(TrainClassifierStep, [feat_form, label_form], {
        "target_label": "grp",
        "method": "rf",
        "cv_folds": 2,
        "random_state": 0,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    signed = out.data[:, stats["signed_score"]]
    assert np.all(imp >= 0)
    assert np.all(signed == 0)
    print("  random forest importance non-negative ok")


def test_single_class_rejected():
    X = np.ones((8, 2), dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    feat_form = _make_features(X, samples, ["A", "B"])
    label_form = _make_labels(["x"] * 8, samples, "grp")
    try:
        run_operator(TrainClassifierStep, [feat_form, label_form], {
            "target_label": "grp", "cv_folds": 2,
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "at least 2 classes" in str(exc)
    print("  single class rejected                ok")


def test_missing_target_label_rejected():
    X = np.random.default_rng(0).normal(size=(8, 2)).astype(np.float32)
    samples = [f"S{i}" for i in range(8)]
    feat_form = _make_features(X, samples, ["A", "B"])
    label_form = _make_labels(["a", "b"] * 4, samples, "grp")
    try:
        run_operator(TrainClassifierStep, [feat_form, label_form], {
            "target_label": "nonexistent", "cv_folds": 2,
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "not in" in str(exc)
    print("  missing target_label rejected        ok")


def test_bad_method_rejected():
    X = np.random.default_rng(0).normal(size=(8, 2)).astype(np.float32)
    samples = [f"S{i}" for i in range(8)]
    feat_form = _make_features(X, samples, ["A", "B"])
    label_form = _make_labels(["a", "b"] * 4, samples, "grp")
    try:
        run_operator(TrainClassifierStep, [feat_form, label_form], {
            "target_label": "grp", "method": "neural_net",
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except (StepError, ValueError):
        pass
    print("  bad method rejected                  ok")


def test_real_proteomics():
    if not (DATA / "proteomics_raw.txt").exists():
        print("  real proteomics (data missing)       skip")
        return
    proteins = read_source(
        DATA / "proteomics_raw.txt",
        dims=["protein", "sample"],
        labels={"protein": {"sample": 0}, "sample": "builtin"},
        reader="csv", sep="\t",
    )
    clinical = read_source(
        DATA / "clinical_raw.txt",
        dims=["sample", "feature"],
        labels={"sample": {"feature": 0}, "feature": "builtin"},
        reader="csv", sep="\t",
    )
    from src.task.step.steps.missing import MissingStep
    from src.task.step.steps.impute import ImputeStep
    from src.task.step.steps.normalize import NormalizeStep
    from src.task.step.steps.log_transform import LogTransformStep
    from src.task.step.steps.transpose import TransposeStep

    f = run_operator(MissingStep, [proteins], {"dim": "protein", "threshold": 0.5})
    f = run_operator(ImputeStep, [f], {"method": "min", "dim": "protein"})
    f = run_operator(NormalizeStep, [f], {"method": "quantile", "dim": "sample"})
    f = run_operator(LogTransformStep, [f], {"base": 2, "pseudocount": 1})
    f = run_operator(TransposeStep, [f], {"order": ["sample", "protein"]})
    out = run_operator(TrainClassifierStep, [f, clinical], {
        "sample_dim": "sample",
        "feature_dim": "protein",
        "label_dim": "feature",
        "target_label": "Stage",
        "method": "logistic",
        "test_size": 0.25,
        "cv_folds": 5,
        "random_state": 42,
        "class_weight": "balanced",
    })
    assert out.dims == ["protein", "statistic"]
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    assert np.all(imp >= 0)
    assert imp.sum() > 0
    print("  real CPTAC proteomics                ok")


def main():
    print("train_classifier verification")
    test_perfect_separation_hand_counted()
    test_random_forest_importance_non_negative()
    test_single_class_rejected()
    test_missing_target_label_rejected()
    test_bad_method_rejected()
    test_real_proteomics()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
