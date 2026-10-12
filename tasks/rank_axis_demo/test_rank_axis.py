# tasks/rank_axis_demo/test_rank_axis.py
"""Correctness tests for rank_axis.

Run:
    python tasks/rank_axis_demo/test_rank_axis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                   # noqa: E402
from src.task.step.steps.rank_axis import RankAxisStep  # noqa: E402


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


def make_form(data, dims=("row", "col")):
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        prefix = d[0].lower()
        labels[d] = {f"{prefix}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = RankAxisStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "rank_axis")], step.export(ctx)


# ------------------------------------------------------------------ #
# Basic top-N selection by variance
# ------------------------------------------------------------------ #

def test_top_n_by_variance():
    """Hand-check: variance of each row.

    r0: [1, 1, 1, 1]       variance = 0
    r1: [0, 10, 0, 10]     variance = 25
    r2: [0, 0, 0, 0]       variance = 0
    r3: [100, 0, 100, 0]   variance = 2500
    r4: [1, 2, 3, 4]       variance = 1.25

    top 2 by variance: r3, r1
    """
    data = np.array([
        [1, 1, 1, 1],
        [0, 10, 0, 10],
        [0, 0, 0, 0],
        [100, 0, 100, 0],
        [1, 2, 3, 4],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "variance", "top_n": 2, "output": "o",
    })
    assert out.data.shape[0] == 2
    assert set(exp["kept_labels"]) == {"r1", "r3"}
    assert exp["n_before"] == 5
    assert exp["n_after"] == 2
    assert exp["n_removed"] == 3
    # Original order preserved
    assert exp["kept_labels"] == ["r1", "r3"]
    print("PASS test_top_n_by_variance")


def test_descending_by_mean():
    """top 2 by mean, descending."""
    data = np.array([
        [1, 2],
        [10, 20],
        [5, 5],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean", "top_n": 2, "output": "o",
    })
    # means: r0=1.5, r1=15, r2=5
    assert set(exp["kept_labels"]) == {"r1", "r2"}
    print("PASS test_descending_by_mean")


def test_ascending():
    """descending=False keeps the smallest values."""
    data = np.array([
        [1, 2],
        [10, 20],
        [5, 5],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean",
        "top_n": 2, "descending": False, "output": "o",
    })
    # means: r0=1.5, r1=15, r2=5
    assert set(exp["kept_labels"]) == {"r0", "r2"}
    print("PASS test_ascending")


# ------------------------------------------------------------------ #
# min_value
# ------------------------------------------------------------------ #

def test_min_value():
    data = np.array([
        [1, 1, 1],    # variance 0
        [1, 2, 3],    # variance ~0.667
        [0, 10, 0],   # variance ~22.2
        [0, 100, 0],  # variance ~2222
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "variance",
        "min_value": 1.0, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r2", "r3"}
    print("PASS test_min_value")


def test_min_value_ascending():
    """descending=False with min_value keeps values <= threshold."""
    data = np.array([
        [1, 2],
        [10, 20],
        [5, 5],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean",
        "min_value": 5.0, "descending": False, "output": "o",
    })
    # means: r0=1.5, r1=15, r2=5
    assert set(exp["kept_labels"]) == {"r0", "r2"}
    print("PASS test_min_value_ascending")


def test_both_top_n_and_min_value():
    """Keep the top 3 by mean, then require >= 5."""
    data = np.array([
        [1, 1],
        [10, 10],
        [2, 2],
        [8, 8],
        [3, 3],
    ], dtype=np.float32)
    # means: r0=1, r1=10, r2=2, r3=8, r4=3
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean",
        "top_n": 3, "min_value": 5.0, "output": "o",
    })
    # top 3 by mean: r1, r3, r4.  min_value >= 5: r1, r3.
    assert set(exp["kept_labels"]) == {"r1", "r3"}
    print("PASS test_both_top_n_and_min_value")


# ------------------------------------------------------------------ #
# Ties
# ------------------------------------------------------------------ #

def test_ties_dropped_by_default():
    data = np.array([
        [0, 0],
        [1, 1],
        [2, 2],
        [3, 3],
        [4, 4],
    ], dtype=np.float32)
    # means: 0, 1, 2, 3, 4
    # top 2: r4, r3
    # also make r2 tied with r3? Not here.
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean", "top_n": 2, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r3", "r4"}
    print("PASS test_ties_dropped_by_default")


def test_keep_ties():
    """When keep_ties=True, all positions sharing the cutoff are kept."""
    data = np.array([
        [5, 5],   # mean 5
        [5, 5],   # mean 5 (tie)
        [5, 5],   # mean 5 (tie)
        [3, 3],   # mean 3
        [1, 1],   # mean 1
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean",
        "top_n": 2, "keep_ties": True, "output": "o",
    })
    # top 2 by mean would be r0, r1, but all three r0/r1/r2 have
    # mean 5, so all three are kept.
    assert set(exp["kept_labels"]) == {"r0", "r1", "r2"}
    print("PASS test_keep_ties")


def test_ties_dropped_without_flag():
    """Without keep_ties, only top_n positions are kept."""
    data = np.array([
        [5, 5],
        [5, 5],
        [5, 5],
        [3, 3],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean", "top_n": 2, "output": "o",
    })
    # Stable sort by descending mean; label order decides ties.
    assert exp["kept_labels"] == ["r0", "r1"]
    print("PASS test_ties_dropped_without_flag")


# ------------------------------------------------------------------ #
# Various statistics
# ------------------------------------------------------------------ #

def test_sum():
    data = np.array([
        [1, 2, 3],   # sum 6
        [10, 0, 0],  # sum 10
        [0, 0, 0],   # sum 0
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "sum", "top_n": 2, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r0", "r1"}
    print("PASS test_sum")


def test_nonzero():
    data = np.array([
        [1, 0, 0],  # nonzero 1
        [1, 2, 3],  # nonzero 3
        [0, 0, 0],  # nonzero 0
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "nonzero", "top_n": 2, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r0", "r1"}
    print("PASS test_nonzero")


def test_abs_mean():
    data = np.array([
        [1, -1],       # abs mean 1
        [10, -10],     # abs mean 10
        [0.5, -0.5],   # abs mean 0.5
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "abs_mean", "top_n": 2, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r0", "r1"}
    print("PASS test_abs_mean")


def test_max():
    data = np.array([
        [1, 5, 3],   # max 5
        [10, 0, 0],  # max 10
        [2, 2, 2],   # max 2
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "max", "top_n": 2, "output": "o",
    })
    assert set(exp["kept_labels"]) == {"r0", "r1"}
    print("PASS test_max")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_excluded():
    data = np.array([
        [1, 2, np.nan, 3],
        [np.nan, np.nan, np.nan, np.nan],
    ], dtype=np.float32)
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "by": "mean", "top_n": 1, "output": "o",
    })
    # r0 mean over {1,2,3} = 2; r1 all NaN, excluded
    assert exp["kept_labels"] == ["r0"]
    assert "r1" not in exp["kept_labels"]
    print("PASS test_nan_excluded")


def test_all_nan_raises():
    data = np.full((3, 3), np.nan, dtype=np.float32)
    form = make_form(data)
    try:
        run(form, {
            "dim": "row", "by": "variance", "top_n": 2, "output": "o",
        })
    except StepError as exc:
        assert "no finite values" in str(exc)
        print("PASS test_all_nan_raises")
        return
    raise AssertionError("did not raise on all-NaN")


# ------------------------------------------------------------------ #
# Axis handling
# ------------------------------------------------------------------ #

def test_rank_col_axis():
    """Rank along 'col' instead of 'row'."""
    data = np.array([
        [0, 100, 1],
        [0, 100, 1],
    ], dtype=np.float32)
    # col variance: c0=0, c1=0, c2=0
    # Better: make a case with different variances
    data = np.array([
        [1, 100, 1],
        [1, 0, 3],
    ], dtype=np.float32)
    # col variances: c0=0, c1=2500, c2=1
    form = make_form(data)
    out, exp = run(form, {
        "dim": "col", "by": "variance", "top_n": 1, "output": "o",
    })
    assert exp["kept_labels"] == ["c1"]
    assert out.data.shape == (2, 1)
    print("PASS test_rank_col_axis")


def test_axis_info_trimmed():
    data = np.array([
        [1, 2, 3],
        [4, 5, 6],
        [7, 8, 9],
    ], dtype=np.float32)
    form = make_form(data)
    form.info["chrom"] = ["chr1", "chr2", "chr3"]
    form.axis_info["row"] = ["chrom"]
    out, _ = run(form, {
        "dim": "row", "by": "sum", "top_n": 2, "output": "o",
    })
    # Rows kept by sum: r2 (24), r1 (15)
    assert out.info["chrom"] == ["chr2", "chr3"]
    print("PASS test_axis_info_trimmed")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_no_selection_raises():
    data = np.array([[1, 2, 3]], dtype=np.float32)
    form = make_form(data)
    try:
        run(form, {
            "dim": "row", "by": "sum",
            "min_value": 100.0, "output": "o",
        })
    except StepError as exc:
        assert "no positions survived" in str(exc)
        print("PASS test_no_selection_raises")
        return
    raise AssertionError("did not raise on empty selection")


def test_bad_params_raise():
    data = np.array([[1, 2, 3]], dtype=np.float32)
    form = make_form(data)
    for bad in (
        {"by": "variance", "top_n": 1},               # no dim
        {"dim": "row", "top_n": 1},                    # no by
        {"dim": "row", "by": "bogus", "top_n": 1},
        {"dim": "row", "by": "variance"},              # no top_n/min_value
        {"dim": "row", "by": "variance", "top_n": 0},
        {"dim": "row", "by": "variance", "top_n": -1},
        {"dim": "nonexistent", "by": "variance", "top_n": 1},
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_top_n_by_variance,
        test_descending_by_mean,
        test_ascending,
        test_min_value,
        test_min_value_ascending,
        test_both_top_n_and_min_value,
        test_ties_dropped_by_default,
        test_keep_ties,
        test_ties_dropped_without_flag,
        test_sum,
        test_nonzero,
        test_abs_mean,
        test_max,
        test_nan_excluded,
        test_all_nan_raises,
        test_rank_col_axis,
        test_axis_info_trimmed,
        test_no_selection_raises,
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