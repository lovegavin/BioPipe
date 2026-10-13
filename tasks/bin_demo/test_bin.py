# tasks/bin_demo/test_bin.py
"""Correctness tests for bin.

Run:
    python tasks/bin_demo/test_bin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError            # noqa: E402
from src.task.step.steps.bin import BinStep     # noqa: E402


class FakeContext:
    def __init__(self, params):
        self.step_params = dict(params)
        self.forms = {}
        self.metadata = {}
        self.memory = None

    def __setitem__(self, name, form):
        form.validate()
        self.forms[name] = form

    def __getitem__(self, name):
        return self.forms[name]


def make_form(data, dims=("row", "col")):
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


def run(form, params):
    ctx = FakeContext(params)
    step = BinStep()
    step.run(ctx, [form])
    return (
        ctx.forms[params.get("output", "bin")],
        step.export(ctx),
    )


def _bin_of(out, i):
    return int(out.data[i, 0])


# ------------------------------------------------------------------ #
# Uniform binning
# ------------------------------------------------------------------ #

def test_uniform_hand_checked():
    """10 values evenly spaced 0..9 -> 5 equal-width bins of size 2.

    Edges at 0, 2, 4, 6, 8, 10. Values [0..9] fall into:
        value 0,1 -> bin 0
        value 2,3 -> bin 1
        value 4,5 -> bin 2
        value 6,7 -> bin 3
        value 8,9 -> bin 4
    """
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    out, exp = run(form, {
        "dim": "row", "bins": 5, "method": "uniform",
        "stat": "mean", "output": "o",
    })
    bins = [_bin_of(out, i) for i in range(10)]
    assert bins == [0, 0, 1, 1, 2, 2, 3, 3, 4, 4], bins
    assert exp["method"] == "uniform"
    assert exp["bins"] == 5
    print("PASS test_uniform_hand_checked")


def test_uniform_two_bins():
    data = np.array([[0.0], [1.0], [2.0], [3.0]])
    form = make_form(data, dims=("row", "col"))
    out, _ = run(form, {
        "dim": "row", "bins": 2, "method": "uniform",
        "stat": "mean", "output": "o",
    })
    bins = [_bin_of(out, i) for i in range(4)]
    assert bins == [0, 0, 1, 1], bins
    print("PASS test_uniform_two_bins")


# ------------------------------------------------------------------ #
# Quantile binning
# ------------------------------------------------------------------ #

def test_quantile_equal_counts():
    """10 distinct values, 5 quantile bins -> 2 per bin."""
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    out, exp = run(form, {
        "dim": "row", "bins": 5, "method": "quantile",
        "stat": "mean", "output": "o",
    })
    bins = [_bin_of(out, i) for i in range(10)]
    # Equal-frequency: values 0,1 -> bin 0; 2,3 -> bin 1; ...
    counts = {}
    for b in bins:
        counts[b] = counts.get(b, 0) + 1
    assert set(counts.values()) == {2}, counts
    print("PASS test_quantile_equal_counts")


def test_quantile_edges_recorded():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    _, exp = run(form, {
        "dim": "row", "bins": 5, "method": "quantile",
        "stat": "mean", "output": "o",
    })
    edges = exp["edges"]
    assert len(edges) == 6
    assert abs(edges[0] - 0.0) < 1e-6
    assert abs(edges[-1] - 9.0) < 1e-6
    print("PASS test_quantile_edges_recorded")


# ------------------------------------------------------------------ #
# Summary statistics
# ------------------------------------------------------------------ #

def test_stat_mean():
    """Two columns, mean decides the bin."""
    data = np.array([
        [0.0, 0.0],   # mean 0
        [0.0, 2.0],   # mean 1
        [2.0, 2.0],   # mean 2
        [4.0, 6.0],   # mean 5
    ])
    form = make_form(data, dims=("row", "col"))
    out, _ = run(form, {
        "dim": "row", "bins": 2, "method": "uniform",
        "stat": "mean", "output": "o",
    })
    # Means: [0, 1, 2, 5]. Two equal-width bins over [0, 5]:
    # 0, 1, 2 -> bin 0; 5 -> bin 1
    bins = [_bin_of(out, i) for i in range(4)]
    assert bins == [0, 0, 0, 1], bins
    print("PASS test_stat_mean")


def test_stat_median():
    """Median vs mean can differ when outliers exist."""
    data = np.array([
        [1.0, 1.0, 1.0],      # median 1
        [100.0, 1.0, 1.0],    # median 1
        [100.0, 100.0, 1.0],  # median 100
    ])
    form = make_form(data, dims=("row", "col"))
    out, _ = run(form, {
        "dim": "row", "bins": 2, "method": "uniform",
        "stat": "median", "output": "o",
    })
    bins = [_bin_of(out, i) for i in range(3)]
    # Medians: [1, 1, 100]. Two bins over [1, 100]: 1 -> bin 0,
    # 100 -> bin 1
    assert bins == [0, 0, 1], bins
    print("PASS test_stat_median")


def test_stat_max_min():
    data = np.array([
        [0.0, 10.0],
        [5.0, 5.0],
        [10.0, 0.0],
    ])
    form = make_form(data, dims=("row", "col"))

    out_max, _ = run(form, {
        "dim": "row", "bins": 3, "method": "uniform",
        "stat": "max", "output": "o",
    })
    # Maxes: [10, 5, 10]. 3 bins over [5, 10]
    assert _bin_of(out_max, 0) > 0
    assert _bin_of(out_max, 1) == 0

    out_min, _ = run(form, {
        "dim": "row", "bins": 3, "method": "uniform",
        "stat": "min", "output": "o",
    })
    # Mins: [0, 5, 0]. 3 bins over [0, 5]
    assert _bin_of(out_min, 0) == 0
    assert _bin_of(out_min, 1) > 0
    print("PASS test_stat_max_min")


def test_stat_first():
    data = np.array([
        [5.0, 0.0],     # first non-nan = 5
        [np.nan, 1.0],  # first non-nan = 1
        [2.0, 3.0],     # first non-nan = 2
    ])
    form = make_form(data, dims=("row", "col"))
    out, _ = run(form, {
        "dim": "row", "bins": 2, "method": "uniform",
        "stat": "first", "output": "o",
    })
    # Firsts: [5, 1, 2]. Two bins over [1, 5]:
    # 1, 2 -> bin 0; 5 -> bin 1
    bins = [_bin_of(out, i) for i in range(3)]
    assert bins == [1, 0, 0], bins
    print("PASS test_stat_first")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_positions_unbinned():
    """Positions whose summary is NaN get bin -1."""
    data = np.array([
        [1.0, 2.0],
        [np.nan, np.nan],   # all NaN
        [3.0, 4.0],
    ])
    form = make_form(data, dims=("row", "col"))
    out, exp = run(form, {
        "dim": "row", "bins": 2, "method": "quantile",
        "stat": "mean", "output": "o",
    })
    assert _bin_of(out, 1) == -1
    assert _bin_of(out, 0) >= 0
    assert exp["n_unbinned"] == 1
    print("PASS test_nan_positions_unbinned")


def test_all_nan_raises():
    data = np.full((3, 2), np.nan, dtype=np.float32)
    form = make_form(data, dims=("row", "col"))
    try:
        run(form, {
            "dim": "row", "bins": 2, "output": "o",
        })
    except StepError as exc:
        assert "fewer than 2" in str(exc)
        print("PASS test_all_nan_raises")
        return
    raise AssertionError("did not raise on all-NaN")


# ------------------------------------------------------------------ #
# Structure
# ------------------------------------------------------------------ #

def test_output_structure():
    data = np.arange(20, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    out, _ = run(form, {
        "dim": "row", "bins": 4, "output": "o",
    })
    assert out.dims == ["row", "bin"]
    assert out.data.shape == (20, 1)
    assert out.labels["row"] == form.labels["row"]
    assert out.labels["bin"] == {"bin": 0}
    print("PASS test_output_structure")


def test_bin_of_label_recorded():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    _, exp = run(form, {
        "dim": "row", "bins": 5, "method": "uniform",
        "stat": "mean", "output": "o",
    })
    bol = exp["bin_of_label"]
    assert len(bol) == 10
    # row0 -> bin 0, row9 -> bin 4
    assert bol["row0"] == 0
    assert bol["row9"] == 4
    print("PASS test_bin_of_label_recorded")


def test_bin_counts_recorded():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    _, exp = run(form, {
        "dim": "row", "bins": 5, "method": "quantile",
        "stat": "mean", "output": "o",
    })
    bc = exp["bin_counts"]
    assert len(bc) == 5
    # Quantile binning on 10 evenly spaced values -> 2 per bin
    for b in bc:
        assert bc[b]["n"] == 2, bc[b]
    print("PASS test_bin_counts_recorded")


# ------------------------------------------------------------------ #
# Degenerate cases
# ------------------------------------------------------------------ #

def test_all_values_equal():
    """All values identical: uniform fallback to a single bin."""
    data = np.full((5, 1), 7.0, dtype=np.float32)
    form = make_form(data, dims=("row", "col"))
    out, exp = run(form, {
        "dim": "row", "bins": 3, "method": "uniform",
        "stat": "mean", "output": "o",
    })
    bins = [_bin_of(out, i) for i in range(5)]
    # All in bin 0
    assert all(b == 0 for b in bins), bins
    print("PASS test_all_values_equal")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.arange(10, dtype=float).reshape(-1, 1)
    form = make_form(data, dims=("row", "col"))
    for bad in (
        {"bins": 5},                                   # no dim
        {"dim": "row"},                                 # ok: bins=10 default
        {"dim": "row", "bins": 1},
        {"dim": "row", "bins": 0},
        {"dim": "row", "method": "bogus"},
        {"dim": "row", "stat": "bogus"},
        {"dim": "nonexistent", "bins": 5},
    ):
        if bad == {"dim": "row"}:
            continue
        try:
            run(form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")

def test_value_label_direct():
    """value_label reads one column from the other axis directly."""
    data = np.array([
        [10.0, 10.0],   # sum column = 10
        [20.0, 20.0],
        [30.0, 30.0],
        [40.0, 40.0],
    ])
    # dims = [row, statistic], with statistic = sum and mean
    form = Form(
        data=data,
        dims=["row", "statistic"],
        labels={
            "row": {f"row{i}": i for i in range(4)},
            "statistic": {"sum": 0, "mean": 1},
        },
        info={"missing_code": np.nan},
    )
    out, exp = run(form, {
        "dim": "row", "bins": 2, "method": "uniform",
        "value_label": "sum", "output": "o",
    })
    # sum column: [10, 20, 30, 40], two bins over [10, 40]:
    # 10, 20 -> bin 0; 30, 40 -> bin 1
    bins = [_bin_of(out, i) for i in range(4)]
    assert bins == [0, 0, 1, 1], bins
    assert exp["value_label"] == "sum"
    assert exp["stat"] is None
    print("PASS test_value_label_direct")


def test_value_label_missing_raises():
    data = np.array([[1.0, 2.0], [3.0, 4.0]])
    form = Form(
        data=data,
        dims=["row", "statistic"],
        labels={
            "row": {"r0": 0, "r1": 1},
            "statistic": {"a": 0, "b": 1},
        },
        info={"missing_code": np.nan},
    )
    try:
        run(form, {
            "dim": "row", "bins": 2,
            "value_label": "nonexistent", "output": "o",
        })
    except StepError as exc:
        assert "value_label" in str(exc)
        print("PASS test_value_label_missing_raises")
        return
    raise AssertionError("did not raise on bad value_label")


def main():
    tests = [
        test_uniform_hand_checked,
        test_uniform_two_bins,
        test_quantile_equal_counts,
        test_quantile_edges_recorded,
        test_stat_mean,
        test_stat_median,
        test_stat_max_min,
        test_stat_first,
        test_nan_positions_unbinned,
        test_all_nan_raises,
        test_output_structure,
        test_bin_of_label_recorded,
        test_bin_counts_recorded,
        test_all_values_equal,
        test_bad_params_raise,
        test_value_label_direct,
        test_value_label_missing_raises
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