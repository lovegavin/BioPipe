"""Independent verification of the regression operators.

Run with: python tasks/verify_ml_regression.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import Form
from src.reader import read_source
from src.reader.readers._encoder import get_encoder
from src.task.step.steps.linear_regression import LinearRegressionStep
from src.task.step.steps.ridge_regression import RidgeRegressionStep
from src.task.step.steps.lasso_regression import LassoRegressionStep
from src.task.step.steps.random_forest_regressor import (
    RandomForestRegressorStep,
)
from src.task.step.steps.gradient_boosting_regressor import (
    GradientBoostingRegressorStep,
)
from src.task.step.steps.missing import MissingStep
from src.task.step.steps.impute import ImputeStep
from src.task.step.steps.normalize import NormalizeStep
from src.task.step.steps.log_transform import LogTransformStep
from src.task.step.steps.transpose import TransposeStep
from biopipe_sdk.testing import run_operator


checks = []


def record(name, ok, expected, actual):
    checks.append((name, bool(ok), str(expected)[:40], str(actual)[:40]))


def section(title):
    print()
    print("=" * 78)
    print(title)
    print("=" * 78)


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


def _numeric(y, samples, name):
    return Form(
        data=np.asarray(y, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "label": {name: 0},
        },
        info={"missing_code": np.nan},
    )


def _sklearn_ols_coef(X, y):
    """Independent closed-form OLS solution."""
    X_int = np.column_stack([np.ones(len(X)), X])
    beta, *_ = np.linalg.lstsq(X_int, y, rcond=None)
    return beta[1:]


def main():
    section("1. Linear regression: coefficients vs closed-form OLS")
    rng = np.random.default_rng(7)
    n = 40
    X = rng.normal(size=(n, 4))
    true_beta = np.array([3.0, -2.0, 0.0, 1.5])
    y = X @ true_beta
    samples = [f"S{i}" for i in range(n)]
    feat = _features(X, samples, ["f0", "f1", "f2", "f3"])
    lab = _numeric(y, samples, "y")

    out = run_operator(LinearRegressionStep, [feat, lab], {
        "target_label": "y", "cv_folds": 3, "scale": False,
    })
    stats = out.labels["statistic"]
    signed = out.data[:, stats["signed_score"]]
    expected = _sklearn_ols_coef(X, y)
    for i in range(4):
        idx = out.labels["feature"][f"f{i}"]
        record(f"f{i}: |coef - OLS| < 1e-3",
                bool(abs(signed[idx] - expected[i]) < 1e-3),
                f"{expected[i]:.4f}", f"{signed[idx]:.4f}")

    section("2. Ridge: |coef| strictly smaller than OLS on same data")
    out_r = run_operator(RidgeRegressionStep, [feat, lab], {
        "target_label": "y", "alpha": 50.0, "cv_folds": 3,
        "scale": False,
    })
    rs = out_r.data[:, out_r.labels["statistic"]["importance"]]
    lin = out.data[:, stats["importance"]]
    record("ridge shrinks total |coef|",
            float(rs.sum()) < float(lin.sum()),
            f"< {lin.sum():.3f}", f"{rs.sum():.3f}")

    section("3. Lasso: sparsity on 20-feature data with one signal")
    rng2 = np.random.default_rng(11)
    n2 = 40
    X2 = rng2.normal(size=(n2, 20))
    y2 = 5.0 * X2[:, 0]
    s2 = [f"S{i}" for i in range(n2)]
    feat2 = _features(X2, s2, [f"f{i}" for i in range(20)])
    lab2 = _numeric(y2, s2, "y")
    out_l = run_operator(LassoRegressionStep, [feat2, lab2], {
        "target_label": "y", "alpha": 0.5, "cv_folds": 3,
    })
    imp_l = out_l.data[:, out_l.labels["statistic"]["importance"]]
    n_zero = int((imp_l < 1e-6).sum())
    record("lasso zeros at least half of 20 features",
            n_zero >= 10, ">= 10", n_zero)
    f0 = out_l.labels["feature"]["f0"]
    record("lasso keeps f0 signal",
            float(imp_l[f0]) > 0.5,
            "> 0.5", f"{float(imp_l[f0]):.4f}")

    section("4. Tree regressors: importance non-negative")
    for cls in (RandomForestRegressorStep,
                GradientBoostingRegressorStep):
        out_t = run_operator(cls, [feat, lab], {
            "target_label": "y", "cv_folds": 3, "random_state": 42,
        })
        imp_t = out_t.data[:, out_t.labels["statistic"]["importance"]]
        record(f"{cls.name}: all importance >= 0",
                bool(np.all(imp_t >= 0)), "all >= 0", "ok")

    section("5. Real CPTAC Age")
    data = Path("tasks/ml_regression_route_demo/input")
    if not (data / "proteomics_raw.txt").exists():
        record("CPTAC data present", False, "present", "missing")
    else:
        proteins = read_source(
            data / "proteomics_raw.txt",
            dims=["protein", "sample"],
            labels={"protein": {"sample": 0}, "sample": "builtin"},
            reader="csv", sep="\t",
        )
        clinical = read_source(
            data / "clinical_raw.txt",
            dims=["sample", "feature"],
            labels={"sample": {"feature": 0}, "feature": "builtin"},
            reader="csv", sep="\t",
        )
        f = run_operator(MissingStep, [proteins],
                          {"dim": "protein", "threshold": 0.5})
        f = run_operator(ImputeStep, [f], {"method": "min",
                                            "dim": "protein"})
        f = run_operator(NormalizeStep, [f],
                          {"method": "quantile", "dim": "sample"})
        f = run_operator(LogTransformStep, [f],
                          {"base": 2, "pseudocount": 1})
        f = run_operator(TransposeStep, [f],
                          {"order": ["sample", "protein"]})
        for cls in (RidgeRegressionStep, RandomForestRegressorStep,
                    GradientBoostingRegressorStep):
            out3 = run_operator(cls, [f, clinical], {
                "sample_dim": "sample", "feature_dim": "protein",
                "label_dim": "feature", "target_label": "Age",
                "test_size": 0.25, "cv_folds": 3,
                "random_state": 42,
            })
            imp = out3.data[:, out3.labels["statistic"]["importance"]]
            record(f"CPTAC Age {cls.name}: dims are [protein, statistic]",
                    out3.dims == ["protein", "statistic"],
                    "['protein', 'statistic']", out3.dims)
            record(f"CPTAC Age {cls.name}: all importance >= 0",
                    bool(np.all(imp >= 0)), "all >= 0", "ok")
            record(f"CPTAC Age {cls.name}: some nonzero importance",
                    float(imp.sum()) > 0, "> 0", f"{float(imp.sum()):.4f}")

    print()
    print("=" * 78)
    print("Verification summary")
    print("=" * 78)
    print(f"{'':<4}{'check':<54}{'expected':>12}{'actual':>14}")
    print("-" * 78)
    for name, ok, exp, act in checks:
        status = "PASS" if ok else "FAIL"
        print(f"{status}  {name:<54}{exp:>12}{act:>14}")
    print("-" * 78)
    passed = sum(1 for _, ok, _, _ in checks if ok)
    print(f"{passed}/{len(checks)} checks passed")
    if passed < len(checks):
        sys.exit(1)


if __name__ == "__main__":
    main()
