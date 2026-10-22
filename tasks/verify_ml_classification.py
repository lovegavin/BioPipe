"""Independent verification of the classification operators.

Run with: python tasks/verify_ml_classification.py
"""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, ".")

from src.core import Form, StepError
from src.reader.readers._encoder import get_encoder
from src.reader import read_source
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


def _labels(values, samples, name):
    enc = get_encoder("labelencoder")
    codes = enc.fit_transform(values)
    return Form(
        data=np.array(codes, dtype=np.float32).reshape(-1, 1),
        dims=["sample", "label"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "label": {name: 0},
        },
        info={"missing_code": np.nan,
              "encoders": {"label": {name: enc}}},
    )


def main():
    section("1. Signal recovery on synthetic 20-feature data")
    rng = np.random.default_rng(123)
    n = 60
    y_idx = np.array([0] * (n // 2) + [1] * (n // 2))
    X = rng.normal(size=(n, 20))
    X[:, 0] += 1.2 * y_idx
    X[:, 1] -= 1.0 * y_idx
    samples = [f"S{i}" for i in range(n)]
    features = [f"F{i}" for i in range(20)]
    feat = _features(X, samples, features)
    lab = _labels(["a"] * (n // 2) + ["b"] * (n // 2), samples, "grp")

    model_specs = [
        (LogisticRegressionStep, "logistic", {"C": 10.0}),
        (RandomForestClassifierStep, "rf", {"n_estimators": 100}),
        (SvmClassifierStep, "svm", {"C": 10.0}),
        (GradientBoostingClassifierStep, "gb", {"n_estimators": 50}),
    ]
    for cls, method, extra in model_specs:
        params = {
            "target_label": "grp", "cv_folds": 5,
            "random_state": 42,
        }
        params.update(extra)
        out = run_operator(cls, [feat, lab], params)
        stats = out.labels["statistic"]
        imp = out.data[:, stats["importance"]]
        signed = out.data[:, stats["signed_score"]]
        record(f"{method}: importance >= 0",
                bool(np.all(imp >= 0)), "all >= 0", "ok")
        if method in ("logistic", "svm"):
            record(f"{method}: importance == |signed|",
                    bool(np.all(np.abs(imp - np.abs(signed)) < 1e-6)),
                    "all equal", "ok")
            top3 = list(np.argsort(-imp)[:3])
            record(f"{method}: signal F0 in top 3",
                    bool(0 in top3),
                    "F0 in top3", f"top3={[int(i) for i in top3]}")
        else:
            record(f"{method}: signed_score is all zero",
                    bool(np.all(signed == 0)), "all zero", "ok")
            top3 = list(np.argsort(-imp)[:3])
            record(f"{method}: signal F0 in top 3",
                    bool(0 in top3),
                    "F0 in top3", f"top3={[int(i) for i in top3]}")

    section("2. Hand-built perfect separation: signs match by hand")
    X2 = np.array([
        [10.0, 1.0], [11.0, 1.0], [12.0, 1.0], [13.0, 1.0],
        [-10.0, 1.0], [-11.0, 1.0], [-12.0, 1.0], [-13.0, 1.0],
    ], dtype=np.float32)
    samples2 = [f"S{i}" for i in range(8)]
    feat2 = _features(X2, samples2, ["A", "B"])
    lab2 = _labels(["c0"] * 4 + ["c1"] * 4, samples2, "grp")
    for cls, method in (
        (LogisticRegressionStep, "logistic"),
        (SvmClassifierStep, "svm"),
    ):
        out2 = run_operator(cls, [feat2, lab2], {
            "target_label": "grp", "cv_folds": 2, "C": 100.0,
        })
        stats = out2.labels["statistic"]
        signed = out2.data[:, stats["signed_score"]]
        imp = out2.data[:, stats["importance"]]
        a = out2.labels["feature"]["A"]
        b = out2.labels["feature"]["B"]
        record(f"{method}: |coef_A| > |coef_B|", bool(imp[a] > imp[b]),
                "A > B", f"{imp[a]:.3f} vs {imp[b]:.3f}")
        record(f"{method}: coef_A < 0", bool(signed[a] < 0),
                "< 0", f"{signed[a]:.4f}")
        record(f"{method}: coef_B == 0 (constant feature)",
                bool(abs(signed[b]) < 1e-6), "0",
                f"{signed[b]:.6f}")

    section("3. Real CPTAC proteomics")
    data = Path("tasks/ml_classification_route_demo/input")
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
        cptac_specs = [
            (LogisticRegressionStep, {"C": 100.0}),
            (RandomForestClassifierStep, {"n_estimators": 200}),
            (GradientBoostingClassifierStep, {"n_estimators": 100}),
        ]
        for cls, extra in cptac_specs:
            params = {
                "sample_dim": "sample", "feature_dim": "protein",
                "label_dim": "feature", "target_label": "Stage",
                "test_size": 0.25, "cv_folds": 3,
                "random_state": 42,
                "valid_labels": ["Stage I", "Stage II", "Stage III"],
            }
            params.update(extra)
            out3 = run_operator(cls, [f, clinical], params)
            stats = out3.labels["statistic"]
            imp = out3.data[:, stats["importance"]]
            nz = int((imp > 0).sum())
            top_k = max(10, int(0.1 * imp.size))
            frac = float(np.sort(imp)[-top_k:].sum() / imp.sum()
                          ) if imp.sum() > 0 else 0.0
            record(f"CPTAC {cls.name}: dims are [protein, statistic]",
                    out3.dims == ["protein", "statistic"],
                    "['protein', 'statistic']", out3.dims)
            record(f"CPTAC {cls.name}: > 100 nonzero importances",
                    nz > 100, "> 100", nz)
            record(f"CPTAC {cls.name}: top 10% share >= 0.2",
                    frac >= 0.2, ">= 0.2", f"{frac:.3f}")

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
