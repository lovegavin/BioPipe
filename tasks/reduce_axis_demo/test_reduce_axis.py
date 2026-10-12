# tasks/reduce_axis_demo/test_reduce_axis.py
"""Correctness tests for reduce_axis.

Run:
    python tasks/reduce_axis_demo/test_reduce_axis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                  # noqa: E402
from src.task.step.steps.reduce_axis import (          # noqa: E402
    ReduceAxisStep,
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


def make_form(data, dims=("row", "col"), info=None, axis_info=None):
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {f"{d}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info=info if info is not None else {"missing_code": np.nan},
        axis_info=axis_info if axis_info is not None else {},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = ReduceAxisStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "reduce_axis")], step.export(ctx)


# ------------------------------------------------------------------ #
# 2D basic stats, hand-checked
# ------------------------------------------------------------------ #

def test_sum_along_col():
    """Reduce along 'col'; each row's values are summed."""
    data = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])
    form = make_form(data)
    out, exp = run(form, {
        "dim": "col", "stats": ["sum"], "output": "o",
    })
    # Row sums: 6, 15
    assert out.data.shape == (2, 1)
    assert np.allclose(out.data[:, 0], [6.0, 15.0])
    assert out.dims == ["row", "statistic"]
    assert out.labels["statistic"] == {"sum": 0}
    assert exp["n_reduced"] == 3
    assert exp["n_outer"] == 2
    print("PASS test_sum_along_col")


def test_sum_along_row():
    data = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])
    form = make_form(data)
    out, exp = run(form, {
        "dim": "row", "stats": ["sum"], "output": "o",
    })
    # Column sums: 5, 7, 9
    assert out.data.shape == (3, 1)
    assert np.allclose(out.data[:, 0], [5.0, 7.0, 9.0])
    assert out.dims == ["col", "statistic"]
    print("PASS test_sum_along_row")


def test_mean_hand():
    data = np.array([
        [1.0, 2.0, 3.0, 4.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["mean"], "output": "o",
    })
    assert abs(out.data[0, 0] - 2.5) < 1e-6
    print("PASS test_mean_hand")


def test_std_hand():
    data = np.array([[1.0, 2.0, 3.0, 4.0]])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["std"], "output": "o",
    })
    # Population std of 1..4 = sqrt(1.25) ≈ 1.1180
    assert abs(out.data[0, 0] - 1.1180339887) < 1e-5
    print("PASS test_std_hand")


def test_var_hand():
    data = np.array([[1.0, 2.0, 3.0, 4.0]])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["var"], "output": "o",
    })
    assert abs(out.data[0, 0] - 1.25) < 1e-6
    print("PASS test_var_hand")


def test_min_max_median():
    data = np.array([
        [3.0, 1.0, 4.0, 1.0, 5.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["min", "max", "median"], "output": "o",
    })
    # min=1, max=5, median=3
    assert abs(out.data[0, 0] - 1.0) < 1e-6
    assert abs(out.data[0, 1] - 5.0) < 1e-6
    assert abs(out.data[0, 2] - 3.0) < 1e-6
    assert out.labels["statistic"] == {"min": 0, "max": 1, "median": 2}
    print("PASS test_min_max_median")


def test_nonzero_hand():
    data = np.array([
        [0.0, 1.0, 0.0, 2.0, 3.0],
        [1.0, 0.0, 0.0, 0.0, 1.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["nonzero"], "output": "o",
    })
    # Row 0: 3 non-zeros; Row 1: 2 non-zeros
    assert np.allclose(out.data[:, 0], [3.0, 2.0])
    print("PASS test_nonzero_hand")


def test_count_hand_with_nan():
    data = np.array([
        [1.0, np.nan, 3.0, np.nan],
        [1.0, 2.0, 3.0, 4.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["count"], "output": "o",
    })
    assert np.allclose(out.data[:, 0], [2.0, 4.0])
    print("PASS test_count_hand_with_nan")


# ------------------------------------------------------------------ #
# NaN semantics
# ------------------------------------------------------------------ #

def test_nan_excluded_from_sum_mean():
    data = np.array([
        [1.0, 2.0, np.nan, np.nan],   # valid: 1, 2
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["sum", "mean"], "output": "o",
    })
    assert abs(out.data[0, 0] - 3.0) < 1e-6        # sum
    assert abs(out.data[0, 1] - 1.5) < 1e-6        # mean
    print("PASS test_nan_excluded_from_sum_mean")


def test_all_nan_row():
    data = np.array([
        [np.nan, np.nan, np.nan],
        [1.0, 2.0, 3.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col",
        "stats": ["sum", "mean", "count", "nonzero"],
        "output": "o",
    })
    # Row 0: sum=0 (nansum), mean=nan, count=0, nonzero=0
    assert out.data[0, 0] == 0.0
    assert np.isnan(out.data[0, 1])
    assert out.data[0, 2] == 0.0
    assert out.data[0, 3] == 0.0
    print("PASS test_all_nan_row")


def test_missing_code_not_nan():
    """missing_code can be a finite value like -1."""
    data = np.array([
        [1.0, -1.0, 3.0],
        [1.0, 2.0, 3.0],
    ])
    form = make_form(
        data, info={"missing_code": -1.0},
    )
    out, _ = run(form, {
        "dim": "col", "stats": ["sum", "count"], "output": "o",
    })
    # Row 0: valid = 1, 3 -> sum=4, count=2
    assert abs(out.data[0, 0] - 4.0) < 1e-6
    assert out.data[0, 1] == 2.0
    print("PASS test_missing_code_not_nan")


# ------------------------------------------------------------------ #
# Multiple stats and axis order
# ------------------------------------------------------------------ #

def test_multiple_stats_order():
    data = np.array([
        [1.0, 2.0, 3.0],
        [10.0, 20.0, 30.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col",
        "stats": ["mean", "sum", "max"],
        "output": "o",
    })
    # Row 0: mean=2, sum=6, max=3
    assert np.allclose(out.data[0], [2.0, 6.0, 3.0])
    # Row 1: mean=20, sum=60, max=30
    assert np.allclose(out.data[1], [20.0, 60.0, 30.0])
    assert list(out.labels["statistic"].keys()) == ["mean", "sum", "max"]
    print("PASS test_multiple_stats_order")


def test_single_stat_as_string():
    data = np.array([[1.0, 2.0, 3.0]])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": "sum", "output": "o",
    })
    assert abs(out.data[0, 0] - 6.0) < 1e-6
    print("PASS test_single_stat_as_string")


# ------------------------------------------------------------------ #
# 3D input
# ------------------------------------------------------------------ #

def test_3d_middle_axis():
    rng = np.random.default_rng(0)
    data = rng.normal(size=(4, 3, 5)).astype(np.float32)
    form = Form(
        data=data,
        dims=["a", "b", "c"],
        labels={
            "a": {f"a{i}": i for i in range(4)},
            "b": {f"b{i}": i for i in range(3)},
            "c": {f"c{i}": i for i in range(5)},
        },
        info={"missing_code": np.nan},
    )
    out, exp = run(form, {
        "dim": "b", "stats": ["sum"], "output": "o",
    })
    assert out.dims == ["a", "c", "statistic"]
    assert out.data.shape == (4, 5, 1)
    # Hand-check a[1, 3] = sum over b of data[1, :, 3]
    expected = data[1, :, 3].sum()
    assert abs(out.data[1, 3, 0] - expected) < 1e-4
    print("PASS test_3d_middle_axis")


def test_3d_first_axis():
    rng = np.random.default_rng(1)
    data = rng.normal(size=(3, 4, 5)).astype(np.float32)
    form = Form(
        data=data,
        dims=["a", "b", "c"],
        labels={
            "a": {f"a{i}": i for i in range(3)},
            "b": {f"b{i}": i for i in range(4)},
            "c": {f"c{i}": i for i in range(5)},
        },
        info={"missing_code": np.nan},
    )
    out, _ = run(form, {
        "dim": "a", "stats": ["sum"], "output": "o",
    })
    assert out.dims == ["b", "c", "statistic"]
    assert out.data.shape == (4, 5, 1)
    expected = data[:, 2, 4].sum()
    assert abs(out.data[2, 4, 0] - expected) < 1e-4
    print("PASS test_3d_first_axis")


# ------------------------------------------------------------------ #
# axis_info handling
# ------------------------------------------------------------------ #

def test_axis_info_dropped_for_reduced_dim():
    data = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])
    form = make_form(
        data,
        info={
            "missing_code": np.nan,
            "chrom": ["chr1", "chr2"],
            "note": "keep me",
        },
        axis_info={"row": ["chrom"]},
    )
    out, _ = run(form, {
        "dim": "row", "stats": ["sum"], "output": "o",
    })
    # chrom was parallel to 'row', so it's gone
    assert "chrom" not in out.info
    assert "note" in out.info
    assert "row" not in out.axis_info
    print("PASS test_axis_info_dropped_for_reduced_dim")


def test_axis_info_kept_for_other_dim():
    data = np.array([
        [1.0, 2.0, 3.0],
        [4.0, 5.0, 6.0],
    ])
    form = make_form(
        data,
        info={
            "missing_code": np.nan,
            "chrom": ["chr1", "chr2"],
        },
        axis_info={"row": ["chrom"]},
    )
    out, _ = run(form, {
        "dim": "col", "stats": ["sum"], "output": "o",
    })
    # 'row' still exists, so chrom survives
    assert out.info["chrom"] == ["chr1", "chr2"]
    assert out.axis_info == {"row": ["chrom"]}
    print("PASS test_axis_info_kept_for_other_dim")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1.0, 2.0]])
    form = make_form(data)
    for bad in (
        {},                                   # no dim, no stats
        {"stats": ["sum"]},                   # no dim
        {"dim": "col"},                       # no stats
        {"dim": "nonexistent", "stats": ["sum"]},
        {"dim": "col", "stats": []},
        {"dim": "col", "stats": ["bogus"]},
        {"dim": "col", "stats": ["sum", "sum"]},   # duplicate
        {"dim": "col", "stats": 5},                # not a list
    ):
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_labels_preserved_for_surviving_dims():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
    ])
    form = make_form(data)
    out, _ = run(form, {
        "dim": "col", "stats": ["sum"], "output": "o",
    })
    assert out.labels["row"] == form.labels["row"]
    print("PASS test_labels_preserved_for_surviving_dims")


def main():
    tests = [
        test_sum_along_col,
        test_sum_along_row,
        test_mean_hand,
        test_std_hand,
        test_var_hand,
        test_min_max_median,
        test_nonzero_hand,
        test_count_hand_with_nan,
        test_nan_excluded_from_sum_mean,
        test_all_nan_row,
        test_missing_code_not_nan,
        test_multiple_stats_order,
        test_single_stat_as_string,
        test_3d_middle_axis,
        test_3d_first_axis,
        test_axis_info_dropped_for_reduced_dim,
        test_axis_info_kept_for_other_dim,
        test_bad_params_raise,
        test_labels_preserved_for_surviving_dims,
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