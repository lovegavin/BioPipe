"""Standalone verification of the classification operators.

Run with: python tasks/ml_classification_route_demo/test_ml_classification.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.logistic_regression import LogisticRegressionStep
from src.task.step.steps.random_forest_classifier import (
    RandomForestClassifierStep,
)
from src.task.step.steps.svm_classifier import SvmClassifierStep
from src.task.step.steps.gradient_boosting_classifier import (
    GradientBoostingClassifierStep,
)
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.impute import ImputeStep
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.transpose import TransposeStep
from biopipe_sdk.testing import run_operator


DATA = Path(__file__).parent / "input"


def _features(X, sample_labels, feature_labels):
    return Form(
        data=np.asarray(X, dtype=np.float32),
        dims=["sample", "feature"],
        labels={
            "sample": {s: i for i, s in enumerate(sample_labels)},
            "feature": {f: i for i, f in enumerate(feature_labels)},
        },
        info={"missing_code": np.nan},
    )


def _labels(values, sample_labels, name):
    enc = get_encoder("labelencoder")
    codes = enc.fit_transform(values)
    return Form(
        data=np.array(codes, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(sample_labels)},
            "label": {name: 0},
        },
        info={"missing_code": np.nan,
              "encoders": {"label": {name: enc}}},
    )


def _perfect_separation():
    """Feature A separates two classes; feature B is constant.

    Expected sign of coef_A is negative: larger A values push toward
    the second class (index 1 in sorted class order).
    """
    X = np.array([
        [10.0, 1.0], [11.0, 1.0], [12.0, 1.0], [13.0, 1.0],
        [-10.0, 1.0], [-11.0, 1.0], [-12.0, 1.0], [-13.0, 1.0],
    ], dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    labels = ["c0"] * 4 + ["c1"] * 4
    return (_features(X, samples, ["A", "B"]),
            _labels(labels, samples, "grp"))


def test_logistic_perfect_separation():
    feat, lab = _perfect_separation()
    out = run_operator(LogisticRegressionStep, [feat, lab], {
        "target_label": "grp", "cv_folds": 2, "C": 100.0,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    signed = out.data[:, stats["signed_score"]]
    a = out.labels["feature"]["A"]
    b = out.labels["feature"]["B"]
    assert imp[a] > imp[b]
    assert signed[a] < 0
    assert abs(signed[b]) < 1e-6
    print("  logistic perfect separation            ok")


def test_rf_importance_non_negative():
    feat, lab = _perfect_separation()
    out = run_operator(RandomForestClassifierStep, [feat, lab], {
        "target_label": "grp", "cv_folds": 2, "n_estimators": 50,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    signed = out.data[:, stats["signed_score"]]
    assert np.all(imp >= 0)
    assert np.all(signed == 0)
    print("  rf importance non-negative             ok")


def test_svm_linear_coefficients():
    feat, lab = _perfect_separation()
    out = run_operator(SvmClassifierStep, [feat, lab], {
        "target_label": "grp", "cv_folds": 2, "C": 100.0,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    signed = out.data[:, stats["signed_score"]]
    a = out.labels["feature"]["A"]
    assert abs(imp[a] - abs(signed[a])) < 1e-6
    assert imp[a] > 1.0
    print("  svm importance == |coef|               ok")


def test_gb_importance():
    feat, lab = _perfect_separation()
    out = run_operator(GradientBoostingClassifierStep, [feat, lab], {
        "target_label": "grp", "cv_folds": 2,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    assert np.all(imp >= 0)
    assert imp.sum() > 0
    print("  gb importance sums positive            ok")


def test_single_class_rejected():
    X = np.ones((8, 2), dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    feat = _features(X, samples, ["A", "B"])
    lab = _labels(["x"] * 8, samples, "grp")
    try:
        run_operator(LogisticRegressionStep, [feat, lab], {
            "target_label": "grp", "cv_folds": 2,
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "at least 2 classes" in str(exc) or ">= 2 classes" in str(exc)
    print("  single class rejected                  ok")


def test_real_cptac():
    if not (DATA / "proteomics_raw.txt").exists():
        print("  real CPTAC (data missing)              skip")
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
    f = run_operator(MissingStep, [proteins],
                      {"dim": "protein", "threshold": 0.5})
    f = run_operator(ImputeStep, [f], {"method": "min", "dim": "protein"})
    f = run_operator(NormalizeStep, [f],
                      {"method": "quantile", "dim": "sample"})
    f = run_operator(LogTransformStep, [f],
                      {"base": 2, "pseudocount": 1})
    f = run_operator(TransposeStep, [f],
                      {"order": ["sample", "protein"]})
    for cls in (LogisticRegressionStep,
                RandomForestClassifierStep,
                GradientBoostingClassifierStep):
        out = run_operator(cls, [f, clinical], {
            "sample_dim": "sample",
            "feature_dim": "protein",
            "label_dim": "feature",
            "target_label": "Stage",
            "test_size": 0.25,
            "cv_folds": 3,
            "random_state": 42,
            "valid_labels": ["Stage I", "Stage II", "Stage III"],
        })
        assert out.dims == ["protein", "statistic"]
        stats = out.labels["statistic"]
        imp = out.data[:, stats["importance"]]
        assert np.all(imp >= 0)
        assert imp.sum() > 0
    print("  real CPTAC: 3 classifiers              ok")


def main():
    print("ML classification operators verification")
    test_logistic_perfect_separation()
    test_rf_importance_non_negative()
    test_svm_linear_coefficients()
    test_gb_importance()
    test_single_class_rejected()
    test_real_cptac()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
