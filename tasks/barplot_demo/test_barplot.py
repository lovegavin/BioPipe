# tasks/barplot_demo/test_barplot.py
"""Correctness tests for barplot.

Run:
    python tasks/barplot_demo/test_barplot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                   # noqa: E402
from src.task.step.steps.barplot import BarplotStep    # noqa: E402


class FakeContext:
    def __init__(self, params, out_dir):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.memory = None
        self.out_dir = Path(out_dir)

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_form(data, dims=("feature", "sample")):
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {f"{d}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )


def run(form, params, tmp_dir="tasks/barplot_demo/output"):
    ctx = FakeContext(params, tmp_dir)
    step = BarplotStep()
    step.run(ctx, [form])
    return step.export(ctx)


# ------------------------------------------------------------------ #
# Basic
# ------------------------------------------------------------------ #

def test_basic_structure():
    data = np.array([
        [1.0, 2.0, 3.0],
        [2.0, 1.0, 1.0],
        [3.0, 2.0, 1.0],
    ])
    form = make_form(data, dims=("feature", "sample"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "top_n": 0,
        "normalize": False,
        "filename": "t.png",
    })
    assert exp["n_features_shown"] == 3
    assert exp["n_samples"] == 3
    assert exp["top_n"] == 0
    print("PASS test_basic_structure")


def test_fraction_sums_to_one():
    """With normalize=True, each sample's fractions sum to 1."""
    rng = np.random.default_rng(0)
    data = rng.uniform(1, 10, size=(5, 4))
    form = make_form(data, dims=("feature", "sample"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "normalize": True,
        "filename": "t.png",
    })
    for sample_label, fractions in exp["per_sample"].items():
        total = sum(fractions.values())
        assert abs(total - 1.0) < 1e-6, (sample_label, total)
    print("PASS test_fraction_sums_to_one")


def test_top_n_aggregates_into_other():
    """top_n selects the largest features; the rest become 'Other'."""
    # Feature totals: f0=100, f1=50, f2=10, f3=1
    data = np.array([
        [50, 50],
        [25, 25],
        [5, 5],
        [0.5, 0.5],
    ])
    form = make_form(data, dims=("feature", "sample"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "top_n": 2,
        "other_label": "Other",
        "normalize": False,
        "filename": "t.png",
    })
    # Top 2 by total: f0 (100) and f1 (50)
    # Shown labels = [f0, f1, Other]
    assert exp["n_features_shown"] == 3
    assert exp["feature_order"] == ["feature0", "feature1", "Other"]
    assert exp["other_label"] == "Other"
    # Sample 0 values in the bar: 50, 25, (5+0.5)=5.5
    s0 = exp["per_sample"]["sample0"]
    assert abs(s0["feature0"] - 50.0) < 1e-5
    assert abs(s0["feature1"] - 25.0) < 1e-5
    assert abs(s0["Other"] - 5.5) < 1e-5
    print("PASS test_top_n_aggregates_into_other")


def test_top_n_orders_by_total():
    """top_n picks the largest totals, in descending order."""
    # f0=1, f1=100, f2=10, f3=50
    data = np.array([
        [1.0, 0.0],
        [100.0, 0.0],
        [10.0, 0.0],
        [50.0, 0.0],
    ])
    form = make_form(data, dims=("feature", "sample"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "top_n": 2, "normalize": False,
        "filename": "t.png",
    })
    # Top 2: f1 (100), f3 (50). f2 (10) and f0 (1) become Other.
    assert exp["feature_order"][:2] == ["feature1", "feature3"]
    assert exp["feature_order"][2] == "Other"
    print("PASS test_top_n_orders_by_total")


# ------------------------------------------------------------------ #
# Orientation
# ------------------------------------------------------------------ #

def test_transposed_input():
    """Input with feature axis second still works."""
    data = np.array([
        [1.0, 2.0, 3.0],   # sample0: f0=1, f1=2, f2=3
        [4.0, 5.0, 6.0],   # sample1: f0=4, f1=5, f2=6
    ])
    form = make_form(data, dims=("sample", "feature"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "top_n": 0, "normalize": False,
        "filename": "t.png",
    })
    assert exp["n_samples"] == 2
    assert exp["n_features_shown"] == 3
    s0 = exp["per_sample"]["sample0"]
    assert abs(s0["feature2"] - 3.0) < 1e-5
    print("PASS test_transposed_input")


# ------------------------------------------------------------------ #
# NaN / negative
# ------------------------------------------------------------------ #

def test_nan_treated_as_zero():
    data = np.array([
        [1.0, np.nan],
        [2.0, 3.0],
    ])
    form = make_form(data, dims=("feature", "sample"))
    exp = run(form, {
        "dim": "feature", "sample_dim": "sample",
        "top_n": 0, "normalize": False,
        "filename": "t.png",
    })
    s0 = exp["per_sample"]["sample0"]
    # feature0 in sample0 was NaN, treated as 0.
    assert abs(s0["feature0"] - 1.0) < 1e-5
    print("PASS test_nan_treated_as_zero")


def test_negative_rejected():
    data = np.array([
        [1.0, -1.0],
        [2.0, 3.0],
    ])
    form = make_form(data, dims=("feature", "sample"))
    try:
        run(form, {
            "dim": "feature", "sample_dim": "sample",
            "filename": "t.png",
        })
    except StepError as exc:
        assert "negative" in str(exc)
        print("PASS test_negative_rejected")
        return
    raise AssertionError("did not raise on negative values")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    form = make_form(data, dims=("feature", "sample"))
    for bad in (
        {"sample_dim": "sample", "filename": "t.png"},   # no dim
        {"dim": "feature", "filename": "t.png"},         # no sample_dim
        {"dim": "feature", "sample_dim": "sample"},      # no filename
        {"dim": "nonexistent", "sample_dim": "sample",
         "filename": "t.png"},
        {"dim": "feature", "sample_dim": "nonexistent",
         "filename": "t.png"},
        {"dim": "feature", "sample_dim": "feature",
         "filename": "t.png"},                            # same dim
        {"dim": "feature", "sample_dim": "sample",
         "filename": "t.png", "top_n": -1},
    ):
        try:
            run(form, bad)
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_empty_matrix_rejected():
    data = np.zeros((0, 3), dtype=np.float32)
    form = Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {},
            "sample": {f"sample{i}": i for i in range(3)},
        },
        info={"missing_code": np.nan},
    )
    try:
        run(form, {
            "dim": "feature", "sample_dim": "sample",
            "filename": "t.png",
        })
    except StepError as exc:
        assert "empty" in str(exc)
        print("PASS test_empty_matrix_rejected")
        return
    raise AssertionError("did not raise on empty matrix")


def main():
    tests = [
        test_basic_structure,
        test_fraction_sums_to_one,
        test_top_n_aggregates_into_other,
        test_top_n_orders_by_total,
        test_transposed_input,
        test_nan_treated_as_zero,
        test_negative_rejected,
        test_bad_params_raise,
        test_empty_matrix_rejected,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except AssertionError as exc:
            failed += 1
            print(f"FAIL {t.__name__}: {exc}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"ERROR {t.__name__}: {type(exc).__name__}: {exc}")
    print()
    print(f"{len(tests) - failed}/{len(tests)} passed")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()