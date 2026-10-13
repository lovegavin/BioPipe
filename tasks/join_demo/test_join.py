# tasks/join_demo/test_join.py
"""Correctness tests for join.

Run:
    python tasks/join_demo/test_join.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError              # noqa: E402
from src.task.step.steps.join import JoinStep     # noqa: E402


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


def make_form(data, row_dim, row_labels, col_dim, col_labels):
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


def run(data_form, meta_form, params):
    ctx = FakeContext(params)
    step = JoinStep()
    step.run(ctx, [data_form, meta_form])
    return (
        ctx.forms[params.get("output", "join")],
        step.export(ctx),
    )


# ------------------------------------------------------------------ #
# Inner join: basic
# ------------------------------------------------------------------ #

def test_inner_join_attaches_columns():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_form(
        data, "sample", ["s0", "s1", "s2"],
        "feature", ["fA", "fB"],
    )
    meta_data = np.array([
        [10.0],
        [20.0],
        [30.0],
    ])
    meta_form = make_form(
        meta_data, "sample", ["s0", "s1", "s2"],
        "meta_feature", ["group"],
    )
    out, exp = run(data_form, meta_form, {
        "dim": "sample", "columns": ["group"],
        "how": "inner", "output": "o",
    })
    assert out.dims == ["sample", "feature"]
    assert out.data.shape == (3, 3)
    # Original data preserved
    assert np.allclose(out.data[:, :2], data)
    # Meta column attached
    assert np.allclose(out.data[:, 2], [10.0, 20.0, 30.0])
    assert set(out.labels["feature"].keys()) == {"fA", "fB", "group"}
    print("PASS test_inner_join_attaches_columns")


def test_multiple_columns():
    data = np.array([[1.0], [2.0]])
    data_form = make_form(
        data, "sample", ["s0", "s1"], "feature", ["x"],
    )
    meta_data = np.array([
        [100.0, 200.0],
        [300.0, 400.0],
    ])
    meta_form = make_form(
        meta_data, "sample", ["s0", "s1"],
        "meta_feature", ["a", "b"],
    )
    out, _ = run(data_form, meta_form, {
        "dim": "sample", "columns": ["a", "b"],
        "how": "inner", "output": "o",
    })
    assert out.data.shape == (2, 3)
    assert np.allclose(out.data[:, 1], [100.0, 300.0])
    assert np.allclose(out.data[:, 2], [200.0, 400.0])
    print("PASS test_multiple_columns")


def test_prefix_disambiguates():
    data = np.array([[1.0]])
    data_form = make_form(
        data, "sample", ["s0"], "feature", ["group"],
    )
    meta_data = np.array([[42.0]])
    meta_form = make_form(
        meta_data, "sample", ["s0"],
        "meta_feature", ["group"],
    )
    # Without prefix, duplicate name
    try:
        run(data_form, meta_form, {
            "dim": "sample", "columns": ["group"],
            "how": "inner", "output": "o",
        })
    except StepError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("did not raise on duplicate label")
    # With prefix, works
    out, _ = run(data_form, meta_form, {
        "dim": "sample", "columns": ["group"],
        "how": "inner", "prefix": "meta_", "output": "o",
    })
    assert "meta_group" in out.labels["feature"]
    print("PASS test_prefix_disambiguates")


# ------------------------------------------------------------------ #
# Label alignment
# ------------------------------------------------------------------ #

def test_inner_keeps_only_common():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_form(
        data, "sample", ["s0", "s1", "s2"], "feature", ["fA", "fB"],
    )
    # Meta only has s1 and s2
    meta_data = np.array([
        [10.0],
        [20.0],
    ])
    meta_form = make_form(
        meta_data, "sample", ["s1", "s2"],
        "meta_feature", ["group"],
    )
    out, exp = run(data_form, meta_form, {
        "dim": "sample", "columns": ["group"],
        "how": "inner", "output": "o",
    })
    assert out.data.shape == (2, 3)
    assert list(out.labels["sample"].keys()) == ["s1", "s2"]
    # Row s1: data was [3, 4], meta was 10
    assert np.allclose(out.data[0, :2], [3.0, 4.0])
    assert out.data[0, 2] == 10.0
    print("PASS test_inner_keeps_only_common")


def test_left_keeps_all_data_rows():
    data = np.array([
        [1.0, 2.0],
        [3.0, 4.0],
        [5.0, 6.0],
    ])
    data_form = make_form(
        data, "sample", ["s0", "s1", "s2"], "feature", ["fA", "fB"],
    )
    meta_data = np.array([[10.0]])
    meta_form = make_form(
        meta_data, "sample", ["s1"],
        "meta_feature", ["group"],
    )
    out, exp = run(data_form, meta_form, {
        "dim": "sample", "columns": ["group"],
        "how": "left", "output": "o",
    })
    # All 3 rows preserved
    assert out.data.shape == (3, 3)
    assert list(out.labels["sample"].keys()) == ["s0", "s1", "s2"]
    # s0 has no match -> NaN
    assert np.isnan(out.data[0, 2])
    # s1 matched
    assert out.data[1, 2] == 10.0
    # s2 also no match
    assert np.isnan(out.data[2, 2])
    assert exp["n_unmatched_rows"] == 2
    print("PASS test_left_keeps_all_data_rows")


def test_row_order_follows_data():
    data = np.array([
        [1.0],
        [2.0],
        [3.0],
    ])
    data_form = make_form(
        data, "sample", ["c", "a", "b"], "feature", ["x"],
    )
    meta_data = np.array([
        [100.0],
        [200.0],
        [300.0],
    ])
    meta_form = make_form(
        meta_data, "sample", ["a", "b", "c"],
        "meta_feature", ["g"],
    )
    out, _ = run(data_form, meta_form, {
        "dim": "sample", "columns": ["g"],
        "how": "inner", "output": "o",
    })
    assert list(out.labels["sample"].keys()) == ["c", "a", "b"]
    # Rows align by label, not by position:
    # data[c]=1 -> meta[c]=300
    # data[a]=2 -> meta[a]=100
    # data[b]=3 -> meta[b]=200
    assert np.allclose(out.data[:, 1], [300.0, 100.0, 200.0])
    print("PASS test_row_order_follows_data")


# ------------------------------------------------------------------ #
# Columns: "all"
# ------------------------------------------------------------------ #

def test_columns_all():
    data = np.array([[1.0]])
    data_form = make_form(
        data, "sample", ["s0"], "feature", ["x"],
    )
    meta_data = np.array([[10.0, 20.0, 30.0]])
    meta_form = make_form(
        meta_data, "sample", ["s0"],
        "meta_feature", ["a", "b", "c"],
    )
    out, exp = run(data_form, meta_form, {
        "dim": "sample", "columns": "all",
        "how": "inner", "output": "o",
    })
    assert out.data.shape == (1, 4)
    assert exp["n_attached_features"] == 3
    print("PASS test_columns_all")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    data = np.array([[1.0]])
    data_form = make_form(
        data, "sample", ["s0"], "feature", ["x"],
    )
    meta_data = np.array([[10.0]])
    meta_form = make_form(
        meta_data, "sample", ["s0"],
        "meta_feature", ["g"],
    )

    for bad in (
        {"columns": ["g"]},                            # no dim
        {"dim": "sample", "how": "bogus"},             # bad how
        {"dim": "sample", "columns": ["nonexistent"]},
        {"dim": "sample", "columns": 5},
        {"dim": "nonexistent", "columns": ["g"]},
    ):
        try:
            run(data_form, meta_form, {**bad, "output": "o"})
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_first_dim_must_be_shared():
    """Both forms must have the shared dim as dims[0]."""
    data = np.array([[1.0, 2.0]])
    # First dim is 'feature' -> wrong
    data_form = make_form(
        data, "feature", ["x"], "sample", ["s0", "s1"],
    )
    meta_data = np.array([[10.0], [20.0]])
    meta_form = make_form(
        meta_data, "sample", ["s0", "s1"],
        "meta_feature", ["g"],
    )
    try:
        run(data_form, meta_form, {
            "dim": "sample", "columns": ["g"], "output": "o",
        })
    except StepError as exc:
        assert "first dim" in str(exc) or "transpose" in str(exc)
        print("PASS test_first_dim_must_be_shared")
        return
    raise AssertionError("did not raise on wrong orientation")


def test_no_common_rows_raises():
    data = np.array([[1.0]])
    data_form = make_form(
        data, "sample", ["s0"], "feature", ["x"],
    )
    meta_data = np.array([[10.0]])
    meta_form = make_form(
        meta_data, "sample", ["s1"],
        "meta_feature", ["g"],
    )
    try:
        run(data_form, meta_form, {
            "dim": "sample", "columns": ["g"],
            "how": "inner", "output": "o",
        })
    except StepError as exc:
        assert "no common" in str(exc)
        print("PASS test_no_common_rows_raises")
        return
    raise AssertionError("did not raise on no common rows")


def main():
    tests = [
        test_inner_join_attaches_columns,
        test_multiple_columns,
        test_prefix_disambiguates,
        test_inner_keeps_only_common,
        test_left_keeps_all_data_rows,
        test_row_order_follows_data,
        test_columns_all,
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