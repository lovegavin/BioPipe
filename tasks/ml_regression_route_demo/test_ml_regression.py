"""Standalone verification of the regression operators.

Run with: python tasks/ml_regression_route_demo/test_ml_regression.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.core import Form, StepError
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.linear_regression import LinearRegressionStep
from src.task.step.steps.ridge_regression import RidgeRegressionStep
from src.task.step.steps.lasso_regression import LassoRegressionStep
from src.task.step.steps.random_forest_regressor import (
    RandomForestRegressorStep,
)
from src.task.step.steps.svm_regressor import SvmRegressorStep
from src.task.step.steps.gradient_boosting_regressor import (
    GradientBoostingRegressorStep,
)
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.impute import ImputeStep
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.transpose import TransposeStep
from biopipe_sdk.testing import run_operator


DATA = Path(__file__).parent / "input"


def _features(X, samples, features):
    return Form(
        data=np.asarray(X, dtype=np.float32),
        dims=["sample", "feature"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "feature": {f: i for i, f in enumerate(features)},
        },
        info={"missing_code": np.nan},
    )


def _numeric_labels(y, samples, name):
    """Numeric target: no encoder registered."""
    return Form(
        data=np.asarray(y, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "label": {name: 0},
        },
        info={"missing_code": np.nan},
    )


def _linear_data():
    """y = 3 * x0 - 2 * x1. Exact recovery expected for OLS."""
    rng = np.random.default_rng(7)
    n = 30
    X = rng.normal(size=(n, 2))
    y = 3.0 * X[:, 0] - 2.0 * X[:, 1]
    samples = [f"S{i}" for i in range(n)]
    return (_features(X, samples, ["x0", "x1"]),
            _numeric_labels(y, samples, "y"))


def test_linear_exact_recovery():
    feat, lab = _linear_data()
    out = run_operator(LinearRegressionStep, [feat, lab], {
        "target_label": "y", "cv_folds": 3, "scale": False,
    })
    stats = out.labels["statistic"]
    signed = out.data[:, stats["signed_score"]]
    imp = out.data[:, stats["importance"]]
    a = out.labels["feature"]["x0"]
    b = out.labels["feature"]["x1"]
    assert abs(signed[a] - 3.0) < 1e-4, signed[a]
    assert abs(signed[b] - (-2.0)) < 1e-4, signed[b]
    assert abs(imp[a] - 3.0) < 1e-4
    assert abs(imp[b] - 2.0) < 1e-4
    print("  linear exact recovery                  ok")


def test_ridge_shrinks_coefficients():
    feat, lab = _linear_data()
    out = run_operator(RidgeRegressionStep, [feat, lab], {
        "target_label": "y", "alpha": 100.0, "cv_folds": 3,
        "scale": False,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    a = out.labels["feature"]["x0"]
    assert imp[a] < 3.0
    assert imp[a] > 0.0
    print("  ridge shrinks coefficients             ok")


def test_lasso_sparsity():
    """Lasso with strong alpha must zero out most features."""
    rng = np.random.default_rng(11)
    n = 40
    X = rng.normal(size=(n, 20))
    y = 5.0 * X[:, 0] + 0.0 * X[:, 1]
    samples = [f"S{i}" for i in range(n)]
    feat = _features(X, samples, [f"f{i}" for i in range(20)])
    lab = _numeric_labels(y, samples, "y")
    out = run_operator(LassoRegressionStep, [feat, lab], {
        "target_label": "y", "alpha": 0.5, "cv_folds": 3,
    })
    stats = out.labels["statistic"]
    imp = out.data[:, stats["importance"]]
    n_zero = int((imp < 1e-6).sum())
    assert n_zero >= 10, n_zero
    a = out.labels["feature"]["f0"]
    assert imp[a] > 0.5
    print(f"  lasso sparsity ({n_zero}/20 zeros)          ok")


def test_rf_and_svr_run():
    feat, lab = _linear_data()
    for cls in (RandomForestRegressorStep, SvmRegressorStep,
                GradientBoostingRegressorStep):
        out = run_operator(cls, [feat, lab], {
            "target_label": "y", "cv_folds": 3,
        })
        stats = out.labels["statistic"]
        imp = out.data[:, stats["importance"]]
        assert np.all(imp >= 0)
        assert imp.sum() > 0
    print("  rf / svr / gb regressors               ok")


def test_categorical_target_rejected():
    X = np.ones((8, 2), dtype=np.float32)
    samples = [f"S{i}" for i in range(8)]
    feat = _features(X, samples, ["a", "b"])
    enc = get_encoder("labelencoder")
    codes = enc.fit_transform(["x", "y"] * 4)
    lab = Form(
        data=np.array(codes, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "label": {"grp": 0},
        },
        info={"missing_code": np.nan,
              "encoders": {"label": {"grp": enc}}},
    )
    try:
        run_operator(LinearRegressionStep, [feat, lab], {
            "target_label": "grp", "cv_folds": 2,
        })
        raise AssertionError("expected rejection")
    except AssertionError:
        raise
    except StepError as exc:
        assert "encoded" in str(exc) or "numeric" in str(exc)
    print("  categorical target rejected            ok")


def test_real_cptac_age():
    if not (DATA / "proteomics_raw.txt").exists():
        print("  real CPTAC Age (data missing)         skip")
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
    for cls in (RidgeRegressionStep, RandomForestRegressorStep,
                GradientBoostingRegressorStep):
        out = run_operator(cls, [f, clinical], {
            "sample_dim": "sample",
            "feature_dim": "protein",
            "label_dim": "feature",
            "target_label": "Age",
            "test_size": 0.25,
            "cv_folds": 3,
            "random_state": 42,
        })
        stats = out.labels["statistic"]
        imp = out.data[:, stats["importance"]]
        assert np.all(imp >= 0)
        assert imp.sum() > 0
    print("  real CPTAC Age: 3 regressors           ok")


def main():
    print("ML regression operators verification")
    test_linear_exact_recovery()
    test_ridge_shrinks_coefficients()
    test_lasso_sparsity()
    test_rf_and_svr_run()
    test_categorical_target_rejected()
    test_real_cptac_age()
    print()
    print("all checks passed")


if __name__ == "__main__":
    main()
