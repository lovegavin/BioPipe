# tasks/compare_groups_demo/test_compare_groups.py
"""Correctness tests for compare_groups.

Run:
    python tasks/compare_groups_demo/test_compare_groups.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                    # noqa: E402
from src.reader.readers._encoder import LabelEncoder    # noqa: E402
from src.task.step.steps.compare_groups import (         # noqa: E402
    CompareGroupsStep,
)


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_forms(counts, groups):
    counts = np.asarray(counts, dtype=np.float32)
    n_features, n_samples = counts.shape
    data_form = Form(
        data=counts,
        dims=["gene", "sample"],
        labels={
            "gene": {f"g{i}": i for i in range(n_features)},
            "sample": {f"s{i}": i for i in range(n_samples)},
        },
        info={"missing_code": np.nan},
    )
    encoder = LabelEncoder()
    codes = encoder.fit_transform(list(groups)).astype(np.float32)
    meta_form = Form(
        data=codes.reshape(-1, 1),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(n_samples)},
            "feature": {"group": 0},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"feature": {"group": encoder}},
        },
    )
    return data_form, meta_form


def run(data_form, meta_form, params):
    ctx = FakeContext(params)
    step = CompareGroupsStep()
    step.run(ctx, [data_form, meta_form])
    return (
        ctx.forms[params.get("output", "compare_groups")],
        step.export(ctx),
    )


# ================================================================== #
# Two-group mode (regression tests for the original behavior)
# ================================================================== #

def test_two_groups_ttest_matches_scipy():
    rng = np.random.default_rng(0)
    n_a, n_b = 6, 6
    counts = rng.uniform(0, 100, size=(4, n_a + n_b)).astype(np.float32)
    groups = ["A"] * n_a + ["B"] * n_b
    data_form, meta_form = make_forms(counts, groups)
    out, exp = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "group_a": "A", "group_b": "B",
        "method": "ttest", "output": "o",
    })
    assert out.dims == ["gene", "statistic"]
    assert out.data.shape == (4, 6)
    for i in range(4):
        ya, yb = counts[i, :n_a], counts[i, n_a:]
        t, p = stats.ttest_ind(yb, ya, equal_var=True)
        assert abs(out.data[i, 3] - t) < 1e-4
        assert abs(out.data[i, 4] - p) < 1e-6
    assert exp["mode"] == "two_groups"
    print("PASS test_two_groups_ttest_matches_scipy")


def test_two_groups_welch_matches_scipy():
    rng = np.random.default_rng(1)
    counts = rng.uniform(0, 100, size=(3, 10)).astype(np.float32)
    groups = ["A"] * 5 + ["B"] * 5
    data_form, meta_form = make_forms(counts, groups)
    out, _ = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "group_a": "A", "group_b": "B",
        "method": "welch", "output": "o",
    })
    for i in range(3):
        t, p = stats.ttest_ind(
            counts[i, 5:], counts[i, :5], equal_var=False
        )
        assert abs(out.data[i, 3] - t) < 1e-4
        assert abs(out.data[i, 4] - p) < 1e-6
    print("PASS test_two_groups_welch_matches_scipy")


def test_two_groups_log2fc_direction():
    counts = np.array([
        [10, 12, 11, 100, 98, 102],    # up in B
        [100, 98, 102, 10, 12, 11],    # up in A
        [50, 52, 51, 50, 51, 52],      # flat
    ], dtype=np.float32)
    groups = ["A"] * 3 + ["B"] * 3
    data_form, meta_form = make_forms(counts, groups)
    out, _ = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "group_a": "A", "group_b": "B",
        "method": "ttest", "output": "o",
    })
    assert out.data[0, 0] > 1.0
    assert out.data[1, 0] < -1.0
    assert abs(out.data[2, 0]) < 0.2
    print("PASS test_two_groups_log2fc_direction")


def test_two_groups_missing_group_raises():
    counts = np.ones((1, 6), dtype=np.float32)
    groups = ["A", "A", "A", "B", "B", "B"]
    data_form, meta_form = make_forms(counts, groups)
    try:
        run(data_form, meta_form, {
            "dim": "gene", "group_dim": "sample",
            "group_label": "group",
            "group_a": "A", "group_b": "Z",
            "method": "ttest", "output": "o",
        })
    except StepError as exc:
        assert "group_b" in str(exc) or "selected" in str(exc)
        print("PASS test_two_groups_missing_group_raises")
        return
    raise AssertionError("did not raise")


# ================================================================== #
# one_vs_rest
# ================================================================== #

def test_one_vs_rest_structure():
    rng = np.random.default_rng(2)
    counts = rng.uniform(0, 100, size=(5, 12)).astype(np.float32)
    groups = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    data_form, meta_form = make_forms(counts, groups)
    out, exp = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "mode": "one_vs_rest", "method": "welch", "output": "o",
    })
    assert out.dims == ["gene", "comparison", "statistic"]
    assert out.data.shape == (5, 3, 6)
    assert set(out.labels["comparison"].keys()) == {"A", "B", "C"}
    assert exp["n_comparisons"] == 3
    assert exp["mode"] == "one_vs_rest"
    print("PASS test_one_vs_rest_structure")


def test_one_vs_rest_matches_direct_welch():
    rng = np.random.default_rng(3)
    counts = rng.uniform(0, 100, size=(3, 9)).astype(np.float32)
    groups = ["A"] * 3 + ["B"] * 3 + ["C"] * 3
    data_form, meta_form = make_forms(counts, groups)
    out, _ = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "mode": "one_vs_rest", "method": "welch", "output": "o",
    })
    ci = out.labels["comparison"]["A"]
    slice_a = out.data[:, ci, :]

    mask_a = np.array([g == "A" for g in groups])
    mask_b = ~mask_a
    for i in range(3):
        ya = counts[i, mask_a]
        yb = counts[i, mask_b]
        t, p = stats.ttest_ind(yb, ya, equal_var=False)
        assert abs(slice_a[i, 3] - t) < 1e-4
        assert abs(slice_a[i, 4] - p) < 1e-6
    print("PASS test_one_vs_rest_matches_direct_welch")


# ================================================================== #
# pairwise
# ================================================================== #

def test_pairwise_structure():
    rng = np.random.default_rng(4)
    counts = rng.uniform(0, 100, size=(4, 12)).astype(np.float32)
    groups = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    data_form, meta_form = make_forms(counts, groups)
    out, exp = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "mode": "pairwise", "method": "welch", "output": "o",
    })
    assert out.data.shape == (4, 3, 6)
    names = set(out.labels["comparison"].keys())
    assert names == {"A_vs_B", "A_vs_C", "B_vs_C"}
    print("PASS test_pairwise_structure")


def test_pairwise_matches_direct_welch():
    rng = np.random.default_rng(5)
    counts = rng.uniform(0, 100, size=(3, 8)).astype(np.float32)
    groups = ["A"] * 4 + ["B"] * 4
    data_form, meta_form = make_forms(counts, groups)
    out, _ = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "mode": "pairwise", "method": "welch", "output": "o",
    })
    assert out.labels["comparison"] == {"A_vs_B": 0}
    slice_ab = out.data[:, 0, :]

    mask_a = np.array([g == "A" for g in groups])
    mask_b = ~mask_a
    for i in range(3):
        ya = counts[i, mask_a]
        yb = counts[i, mask_b]
        t, p = stats.ttest_ind(yb, ya, equal_var=False)
        assert abs(slice_ab[i, 3] - t) < 1e-4
        assert abs(slice_ab[i, 4] - p) < 1e-6
    print("PASS test_pairwise_matches_direct_welch")


# ================================================================== #
# Filtering, skipping, errors
# ================================================================== #

def test_groups_argument_filters():
    rng = np.random.default_rng(6)
    counts = rng.uniform(0, 100, size=(3, 12)).astype(np.float32)
    groups = ["A"] * 4 + ["B"] * 4 + ["C"] * 4
    data_form, meta_form = make_forms(counts, groups)
    out, exp = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "groups": ["B", "C"],
        "mode": "one_vs_rest", "method": "welch", "output": "o",
    })
    assert set(out.labels["comparison"].keys()) == {"B", "C"}
    assert exp["n_comparisons"] == 2
    print("PASS test_groups_argument_filters")


def test_missing_group_in_groups_raises():
    counts = np.zeros((3, 6), dtype=np.float32)
    groups = ["A"] * 3 + ["B"] * 3
    data_form, meta_form = make_forms(counts, groups)
    try:
        run(data_form, meta_form, {
            "dim": "gene", "group_dim": "sample",
            "group_label": "group",
            "groups": ["A", "Z"],
            "mode": "one_vs_rest", "method": "welch", "output": "o",
        })
    except StepError as exc:
        assert "Z" in str(exc)
        print("PASS test_missing_group_in_groups_raises")
        return
    raise AssertionError("did not raise")


def test_small_group_skipped():
    rng = np.random.default_rng(7)
    counts = rng.uniform(0, 100, size=(3, 8)).astype(np.float32)
    groups = ["A"] * 4 + ["B"] * 3 + ["C"] * 1
    data_form, meta_form = make_forms(counts, groups)
    out, exp = run(data_form, meta_form, {
        "dim": "gene", "group_dim": "sample",
        "group_label": "group",
        "mode": "one_vs_rest", "method": "welch",
        "min_per_group": 2, "output": "o",
    })
    assert "C" not in out.labels["comparison"]
    assert exp["n_skipped"] == 1
    assert any(s["comparison"] == "C" for s in exp["skipped"])
    print("PASS test_small_group_skipped")


def test_all_skipped_raises():
    counts = np.zeros((3, 4), dtype=np.float32)
    groups = ["A", "A", "B", "B"]
    data_form, meta_form = make_forms(counts, groups)
    try:
        run(data_form, meta_form, {
            "dim": "gene", "group_dim": "sample",
            "group_label": "group",
            "mode": "one_vs_rest", "method": "welch",
            "min_per_group": 10, "output": "o",
        })
    except StepError as exc:
        assert "every comparison was skipped" in str(exc)
        print("PASS test_all_skipped_raises")
        return
    raise AssertionError("did not raise")


def test_bad_params_raise():
    counts = np.zeros((3, 6), dtype=np.float32)
    groups = ["A"] * 3 + ["B"] * 3
    data_form, meta_form = make_forms(counts, groups)
    for bad in (
        {"group_dim": "sample", "group_label": "group"},   # no dim
        {"dim": "gene", "group_label": "group"},            # no group_dim
        {"dim": "gene", "group_dim": "sample"},             # no group_label
        {"dim": "gene", "group_dim": "sample",
         "group_label": "group", "mode": "bogus"},
        {"dim": "gene", "group_dim": "sample",
         "group_label": "group", "method": "bogus"},
        {"dim": "gene", "group_dim": "sample",
         "group_label": "group",
         "mode": "two_groups", "method": "welch"},         # missing group_a/b
        {"dim": "gene", "group_dim": "sample",
         "group_label": "group",
         "mode": "one_vs_rest", "method": "welch",
         "min_per_group": 0},
        {"dim": "nonexistent", "group_dim": "sample",
         "group_label": "group"},
    ):
        try:
            run(data_form, meta_form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_two_groups_ttest_matches_scipy,
        test_two_groups_welch_matches_scipy,
        test_two_groups_log2fc_direction,
        test_two_groups_missing_group_raises,
        test_one_vs_rest_structure,
        test_one_vs_rest_matches_direct_welch,
        test_pairwise_structure,
        test_pairwise_matches_direct_welch,
        test_groups_argument_filters,
        test_missing_group_in_groups_raises,
        test_small_group_skipped,
        test_all_skipped_raises,
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