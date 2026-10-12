# tasks/dotplot_demo/test_dotplot.py
"""Correctness tests for dotplot.

Run:
    python tasks/dotplot_demo/test_dotplot.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                  # noqa: E402
from src.reader.readers._encoder import LabelEncoder  # noqa: E402
from src.task.step.steps.dotplot import DotplotStep   # noqa: E402


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


def make_data_form(data, features, samples):
    """data: (n_features, n_samples)."""
    data = np.asarray(data, dtype=np.float32)
    return Form(
        data=data,
        dims=["gene", "cell"],
        labels={
            "gene": {g: i for i, g in enumerate(features)},
            "cell": {s: i for i, s in enumerate(samples)},
        },
        info={"missing_code": np.nan},
    )


def make_meta_form(groups, samples):
    """groups: list of group names per sample."""
    enc = LabelEncoder()
    enc.fit_transform(list(groups))
    codes = enc.fit_transform(list(groups)).astype(np.float32)
    return Form(
        data=codes.reshape(-1, 1),
        dims=["cell", "feature"],
        labels={
            "cell": {s: i for i, s in enumerate(samples)},
            "feature": {"cluster": 0},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"feature": {"cluster": enc}},
        },
    )


def run(data_form, meta_form, params,
        tmp_dir="tasks/dotplot_demo/output"):
    ctx = FakeContext(params, tmp_dir)
    step = DotplotStep()
    step.run(ctx, [data_form, meta_form])
    return step.export(ctx)


# ------------------------------------------------------------------ #
# Basic mean / nonzero
# ------------------------------------------------------------------ #

def test_basic_mean_nonzero():
    """Two features, two groups, hand-computed mean and proportion."""
    samples = ["s0", "s1", "s2", "s3"]
    features = ["fA", "fB"]
    # Data rows are features, columns are samples.
    # fA: [1, 3, 0, 0]   group A: {1,3}   mean=2  prop=1
    #                    group B: {0,0}   mean=0  prop=0
    # fB: [0, 0, 5, 10]  group A: {0,0}   mean=0  prop=0
    #                    group B: {5,10}  mean=7.5 prop=1
    data = np.array([
        [1.0, 3.0, 0.0, 0.0],
        [0.0, 0.0, 5.0, 10.0],
    ])
    groups = ["A", "A", "B", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA", "fB"],
        "statistic": "mean",
        "proportion_mode": "nonzero",
        "filename": "t.png",
    })
    assert exp["groups"] == ["A", "B"]
    assert exp["value"]["A"]["fA"] == 2.0
    assert exp["value"]["A"]["fB"] == 0.0
    assert exp["value"]["B"]["fA"] == 0.0
    assert exp["value"]["B"]["fB"] == 7.5
    assert exp["proportion"]["A"]["fA"] == 1.0
    assert exp["proportion"]["A"]["fB"] == 0.0
    assert exp["proportion"]["B"]["fA"] == 0.0
    assert exp["proportion"]["B"]["fB"] == 1.0
    print("PASS test_basic_mean_nonzero")


def test_median():
    samples = ["s0", "s1", "s2", "s3"]
    features = ["fA"]
    data = np.array([[1.0, 5.0, 10.0, 100.0]])
    groups = ["A", "A", "B", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA"],
        "statistic": "median",
        "filename": "t.png",
    })
    # A: {1, 5} -> median 3
    # B: {10, 100} -> median 55
    assert exp["value"]["A"]["fA"] == 3.0
    assert exp["value"]["B"]["fA"] == 55.0
    print("PASS test_median")


def test_sum():
    samples = ["s0", "s1", "s2"]
    features = ["fA"]
    data = np.array([[1.0, 2.0, 3.0]])
    groups = ["A", "A", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA"],
        "statistic": "sum",
        "filename": "t.png",
    })
    assert exp["value"]["A"]["fA"] == 3.0
    assert exp["value"]["B"]["fA"] == 3.0
    print("PASS test_sum")


# ------------------------------------------------------------------ #
# Proportion modes
# ------------------------------------------------------------------ #

def test_proportion_threshold():
    samples = ["s0", "s1", "s2", "s3"]
    features = ["fA"]
    data = np.array([[0.1, 0.5, 2.0, 5.0]])
    groups = ["A", "A", "B", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA"],
        "proportion_mode": "threshold",
        "threshold": 1.0,
        "filename": "t.png",
    })
    # A: values 0.1, 0.5, none >= 1 -> 0
    # B: values 2.0, 5.0, both >= 1 -> 1
    assert exp["proportion"]["A"]["fA"] == 0.0
    assert exp["proportion"]["B"]["fA"] == 1.0
    print("PASS test_proportion_threshold")


# ------------------------------------------------------------------ #
# Groups argument
# ------------------------------------------------------------------ #

def test_groups_order():
    samples = ["s0", "s1", "s2"]
    features = ["fA"]
    data = np.array([[1.0, 1.0, 1.0]])
    groups = ["A", "B", "C"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA"],
        "groups": ["C", "A", "B"],
        "filename": "t.png",
    })
    assert exp["groups"] == ["C", "A", "B"]
    print("PASS test_groups_order")


def test_missing_group_raises():
    samples = ["s0", "s1"]
    features = ["fA"]
    data = np.array([[1.0, 1.0]])
    groups = ["A", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    try:
        run(data_form, meta_form, {
            "feature_dim": "gene",
            "group_dim": "cell",
            "group_label": "cluster",
            "features": ["fA"],
            "groups": ["A", "Z"],
            "filename": "t.png",
        })
    except StepError as exc:
        assert "Z" in str(exc)
        print("PASS test_missing_group_raises")
        return
    raise AssertionError("did not raise")


# ------------------------------------------------------------------ #
# Feature selection
# ------------------------------------------------------------------ #

def test_feature_subset():
    samples = ["s0", "s1"]
    features = ["fA", "fB", "fC"]
    data = np.array([
        [1.0, 1.0],
        [2.0, 2.0],
        [3.0, 3.0],
    ])
    groups = ["A", "A"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fC", "fA"],
        "filename": "t.png",
    })
    assert exp["features"] == ["fC", "fA"]
    assert exp["n_features"] == 2
    print("PASS test_feature_subset")


def test_missing_feature_raises():
    samples = ["s0", "s1"]
    features = ["fA"]
    data = np.array([[1.0, 1.0]])
    groups = ["A", "A"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    try:
        run(data_form, meta_form, {
            "feature_dim": "gene",
            "group_dim": "cell",
            "group_label": "cluster",
            "features": ["fA", "nonexistent"],
            "filename": "t.png",
        })
    except StepError as exc:
        assert "nonexistent" in str(exc)
        print("PASS test_missing_feature_raises")
        return
    raise AssertionError("did not raise")


# ------------------------------------------------------------------ #
# NaN
# ------------------------------------------------------------------ #

def test_nan_skipped():
    samples = ["s0", "s1", "s2", "s3"]
    features = ["fA"]
    data = np.array([[1.0, np.nan, np.nan, 3.0]])
    groups = ["A", "A", "B", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)
    exp = run(data_form, meta_form, {
        "feature_dim": "gene",
        "group_dim": "cell",
        "group_label": "cluster",
        "features": ["fA"],
        "filename": "t.png",
    })
    # A: only 1.0 -> mean 1, prop 1
    # B: only 3.0 -> mean 3, prop 1
    assert exp["value"]["A"]["fA"] == 1.0
    assert exp["value"]["B"]["fA"] == 3.0
    assert exp["proportion"]["A"]["fA"] == 1.0
    assert exp["proportion"]["B"]["fA"] == 1.0
    print("PASS test_nan_skipped")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    samples = ["s0", "s1"]
    features = ["fA"]
    data = np.array([[1.0, 1.0]])
    groups = ["A", "B"]
    data_form = make_data_form(data, features, samples)
    meta_form = make_meta_form(groups, samples)

    for bad in (
        {"group_dim": "cell", "features": ["fA"],
         "group_label": "cluster", "filename": "t.png"},  # no feature_dim
        {"feature_dim": "gene", "features": ["fA"],
         "group_label": "cluster", "filename": "t.png"},  # no group_dim
        {"feature_dim": "gene", "group_dim": "cell",
         "group_label": "cluster", "filename": "t.png"},  # no features
        {"feature_dim": "gene", "group_dim": "cell",
         "features": ["fA"], "filename": "t.png"},         # no group_label
        {"feature_dim": "gene", "group_dim": "cell",
         "features": ["fA"], "group_label": "cluster"},    # no filename
        {"feature_dim": "gene", "group_dim": "cell",
         "features": [], "group_label": "cluster",
         "filename": "t.png"},                              # empty features
        {"feature_dim": "gene", "group_dim": "cell",
         "features": ["fA"], "group_label": "cluster",
         "filename": "t.png", "statistic": "bogus"},
        {"feature_dim": "gene", "group_dim": "cell",
         "features": ["fA"], "group_label": "cluster",
         "filename": "t.png", "proportion_mode": "bogus"},
    ):
        try:
            run(data_form, meta_form, bad)
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_basic_mean_nonzero,
        test_median,
        test_sum,
        test_proportion_threshold,
        test_groups_order,
        test_missing_group_raises,
        test_feature_subset,
        test_missing_feature_raises,
        test_nan_skipped,
        test_bad_params_raise,
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