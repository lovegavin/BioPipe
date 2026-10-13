# tasks/aggregate_demo/test_aggregate.py
"""Correctness tests for aggregate.

Run:
    python tasks/aggregate_demo/test_aggregate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                 # noqa: E402
from src.reader.readers._encoder import LabelEncoder # noqa: E402
from src.task.step.steps.aggregate import (           # noqa: E402
    AggregateStep,
)


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


def make_data_form(data, row_labels, col_labels,
                   row_dim="row", col_dim="col"):
    data = np.asarray(data, dtype=np.float32)
    return Form(
        data=data,
        dims=[row_dim, col_dim],
        labels={
            row_dim: {l: i for i, l in enumerate(row_labels)},
            col_dim: {l: i for i, l in enumerate(col_labels)},
        },
        info={"missing_code": np.nan},
    )


def make_groups_form(codes, row_labels, group_col="group",
                     row_dim="row", group_dim="feature",
                     encoder=None):
    data = np.asarray(codes, dtype=np.float32).reshape(-1, 1)
    info = {"missing_code": np.nan}
    if encoder is not None:
        info["encoders"] = {
            group_dim: {group_col: encoder},
        }
    return Form(
        data=data,
        dims=[row_dim, group_dim],
        labels={
            row_dim: {l: i for i, l in enumerate(row_labels)},
            group_dim: {group_col: 0},
        },
        info=info,
    )


def run(data_form, groups_form, params):
    ctx = FakeContext(params)
    step = AggregateStep()
    step.run(ctx, [data_form, groups_form])
    return (
        ctx.forms[params.get("output", "aggregate")],
        step.export(ctx),
    )


# ------------------------------------------------------------------ #
# Numeric groups, hand-checked
# ------------------------------------------------------------------ #

def test_sum_hand_checked():
    """Two rows in group 0, one row in group 1.

    Rows:
        r0: [1, 2]   group 0
        r1: [3, 4]   group 0
        r2: [5, 6]   group 1

    group 0 sum: [4, 6]
    group 1 sum: [5, 6]
    """
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0, 0, 1], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, exp = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    assert out.dims == ["meta", "feature"]
    assert out.data.shape == (2, 2)
    assert np.allclose(out.data[0], [4.0, 6.0])
    assert np.allclose(out.data[1], [5.0, 6.0])
    assert exp["n_groups"] == 2
    print("PASS test_sum_hand_checked")


def test_mean_hand_checked():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0, 0, 1], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "mean", "output": "o",
    })
    # group 0: [2, 3], group 1: [5, 6]
    assert np.allclose(out.data[0], [2.0, 3.0])
    assert np.allclose(out.data[1], [5.0, 6.0])
    print("PASS test_mean_hand_checked")


def test_median_hand_checked():
    data = np.array([
        [1.0, 10.0],
        [2.0, 20.0],
        [100.0, 30.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0, 0, 0], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "median", "output": "o",
    })
    # Column a: median of {1, 2, 100} = 2
    # Column b: median of {10, 20, 30} = 20
    assert np.allclose(out.data[0], [2.0, 20.0])
    print("PASS test_median_hand_checked")


def test_min_max():
    data = np.array([
        [1.0, 10.0],
        [3.0, 5.0],
        [5.0, 30.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0, 0, 0], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out_min, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "min", "output": "o",
    })
    out_max, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "max", "output": "o",
    })
    assert np.allclose(out_min.data[0], [1.0, 5.0])
    assert np.allclose(out_max.data[0], [5.0, 30.0])
    print("PASS test_min_max")


def test_count():
    data = np.array([
        [1.0, np.nan],
        [2.0, 3.0],
        [np.nan, 4.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0, 0, 0], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "count", "output": "o",
    })
    # Column a: r0=1 valid, r1=2 valid, r2=NaN -> count = 2
    # Column b: r0=NaN, r1=3 valid, r2=4 valid -> count = 2
    assert np.allclose(out.data[0], [2.0, 2.0])
    print("PASS test_count")


# ------------------------------------------------------------------ #
# Encoded group labels
# ------------------------------------------------------------------ #

def test_encoded_groups():
    """String groups are encoded in the metadata form, decoded by
    the operator."""
    data = np.array([
        [1.0],
        [2.0],
        [3.0],
        [4.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2", "r3"], ["x"],
        row_dim="sample", col_dim="feature",
    )
    enc = LabelEncoder()
    raw_groups = ["A", "A", "B", "B"]
    codes = enc.fit_transform(raw_groups)
    groups_form = make_groups_form(
        codes, ["r0", "r1", "r2", "r3"],
        row_dim="sample", group_dim="meta",
        encoder=enc,
    )
    out, exp = run(data_form, groups_form, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    assert set(out.labels["meta"].keys()) == {"A", "B"}
    # A: 1+2 = 3, B: 3+4 = 7
    assert np.allclose(out.data[0, 0], 3.0)
    assert np.allclose(out.data[1, 0], 7.0)
    print("PASS test_encoded_groups")


# ------------------------------------------------------------------ #
# Row alignment
# ------------------------------------------------------------------ #

def test_label_alignment():
    """Only common row labels are aggregated; row order follows
    data form."""
    data = np.array([
        [1.0],   # c
        [2.0],   # a
        [3.0],   # b
    ])
    data_form = make_data_form(
        data, ["c", "a", "b"], ["x"],
        row_dim="sample", col_dim="feature",
    )
    # Groups form has rows in a different order
    groups_codes = [100.0, 200.0, 100.0]  # a->100, b->200, c->100
    groups = make_groups_form(
        groups_codes, ["a", "b", "c"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    # Aligned:
    #   c -> group 100, value 1
    #   a -> group 100, value 2
    #   b -> group 200, value 3
    # group 100 sum: 1+2 = 3
    # group 200 sum: 3
    assert "100" in out.labels["meta"]
    assert "200" in out.labels["meta"]
    g100 = out.labels["meta"]["100"]
    g200 = out.labels["meta"]["200"]
    assert abs(out.data[g100, 0] - 3.0) < 1e-6
    assert abs(out.data[g200, 0] - 3.0) < 1e-6
    print("PASS test_label_alignment")


def test_group_order_first_appearance():
    """Group labels are sorted by first appearance in the input."""
    data = np.array([[1.0], [2.0], [3.0]])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["x"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [50.0, 10.0, 50.0], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    # 50 first (r0), then 10 (r1)
    assert list(out.labels["meta"].keys()) == ["50", "10"]
    print("PASS test_group_order_first_appearance")


def test_group_sizes_recorded():
    data = np.array([[1.0], [2.0], [3.0], [4.0]])
    data_form = make_data_form(
        data, ["r0", "r1", "r2", "r3"], ["x"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0.0, 0.0, 1.0, 1.0], ["r0", "r1", "r2", "r3"],
        row_dim="sample", group_dim="meta",
    )
    _, exp = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    assert exp["group_sizes"]["0"] == 2
    assert exp["group_sizes"]["1"] == 2
    print("PASS test_group_sizes_recorded")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_excluded_from_sum():
    """NaN cells do not contribute to the sum."""
    data = np.array([
        [1.0, np.nan],
        [2.0, 3.0],
        [np.nan, 4.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1", "r2"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0.0, 0.0, 0.0], ["r0", "r1", "r2"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "sum", "output": "o",
    })
    # Column a: 1+2 = 3; Column b: 3+4 = 7
    assert np.allclose(out.data[0], [3.0, 7.0])
    print("PASS test_nan_excluded_from_sum")


def test_all_nan_row_in_group():
    data = np.array([
        [np.nan, np.nan],
        [1.0, 2.0],
    ])
    data_form = make_data_form(
        data, ["r0", "r1"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0.0, 0.0], ["r0", "r1"],
        row_dim="sample", group_dim="meta",
    )
    out, _ = run(data_form, groups, {
        "dim": "sample", "group_col": "group",
        "method": "mean", "output": "o",
    })
    # Mean of only the valid row
    assert np.allclose(out.data[0], [1.0, 2.0])
    print("PASS test_all_nan_row_in_group")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1.0, 2.0]])
    data_form = make_data_form(
        data, ["r0"], ["a", "b"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0.0], ["r0"],
        row_dim="sample", group_dim="meta",
    )
    for bad in (
        {"group_col": "group"},                        # no dim
        {"dim": "sample"},                              # no group_col
        {"dim": "sample", "group_col": "group",
         "method": "bogus"},
        {"dim": "sample", "group_col": "nonexistent"},
        {"dim": "nonexistent", "group_col": "group"},
    ):
        try:
            run(data_form, groups, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_first_dim_must_be_shared():
    data = np.array([[1.0, 2.0]])
    # First dim is 'feature' (wrong)
    data_form = make_data_form(
        data, ["f0"], ["s0", "s1"],
        row_dim="feature", col_dim="sample",
    )
    groups = make_groups_form(
        [0.0, 0.0], ["s0", "s1"],
        row_dim="sample", group_dim="meta",
    )
    try:
        run(data_form, groups, {
            "dim": "sample", "group_col": "group", "output": "o",
        })
    except StepError as exc:
        assert "first dim" in str(exc) or "transpose" in str(exc)
        print("PASS test_first_dim_must_be_shared")
        return
    raise AssertionError("did not raise on wrong orientation")


def test_no_common_rows_raises():
    data = np.array([[1.0]])
    data_form = make_data_form(
        data, ["s0"], ["x"],
        row_dim="sample", col_dim="feature",
    )
    groups = make_groups_form(
        [0.0], ["s1"],
        row_dim="sample", group_dim="meta",
    )
    try:
        run(data_form, groups, {
            "dim": "sample", "group_col": "group", "output": "o",
        })
    except StepError as exc:
        assert "no common" in str(exc)
        print("PASS test_no_common_rows_raises")
        return
    raise AssertionError("did not raise on no common rows")


def main():
    tests = [
        test_sum_hand_checked,
        test_mean_hand_checked,
        test_median_hand_checked,
        test_min_max,
        test_count,
        test_encoded_groups,
        test_label_alignment,
        test_group_order_first_appearance,
        test_group_sizes_recorded,
        test_nan_excluded_from_sum,
        test_all_nan_row_in_group,
        test_bad_params_raise,
        test_first_dim_must_be_shared,
        test_no_common_rows_raises,
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