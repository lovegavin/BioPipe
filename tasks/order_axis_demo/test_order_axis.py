# tasks/order_axis_demo/test_order_axis.py
"""Correctness tests for order_axis.

Run:
    python tasks/order_axis_demo/test_order_axis.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                       # noqa: E402
from src.task.step.steps.order_axis import OrderAxisStep   # noqa: E402


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


def make_form(data, dims=("row", "col"), info=None, axis_info=None):
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {f"{d}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info=dict(info or {"missing_code": np.nan}),
        axis_info={k: list(v) for k, v in (axis_info or {}).items()},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = OrderAxisStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "order_axis")], step.export(ctx)


# ------------------------------------------------------------------ #
# Basic ordering
# ------------------------------------------------------------------ #

def test_ascending_reorders_all():
    data = np.array([[30.0], [10.0], [50.0], [20.0], [40.0]])
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": [30, 10, 50, 20, 40]},
        axis_info={"row": ["score"]},
    )
    out, exp = run(form, {
        "dim": "row", "by": "score", "output": "o",
    })
    # Ascending: row1 (10), row3 (20), row0 (30), row4 (40), row2 (50)
    assert out.data.flatten().tolist() == [10.0, 20.0, 30.0, 40.0, 50.0]
    assert out.labels["row"] == {
        "row1": 0, "row3": 1, "row0": 2, "row4": 3, "row2": 4,
    }
    assert exp["order"][0]["label"] == "row1"
    print("PASS test_ascending_reorders_all")


def test_descending_reorders_all():
    data = np.array([[30.0], [10.0], [50.0], [20.0], [40.0]])
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": [30, 10, 50, 20, 40]},
        axis_info={"row": ["score"]},
    )
    out, _ = run(form, {
        "dim": "row", "by": "score",
        "descending": True, "output": "o",
    })
    assert out.data.flatten().tolist() == [50.0, 40.0, 30.0, 20.0, 10.0]
    assert out.labels["row"]["row2"] == 0
    print("PASS test_descending_reorders_all")


# ------------------------------------------------------------------ #
# All positions preserved
# ------------------------------------------------------------------ #

def test_all_positions_preserved():
    data = np.arange(8).reshape(8, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": list(range(8))[::-1]},
        axis_info={"row": ["score"]},
    )
    out, _ = run(form, {"dim": "row", "by": "score", "output": "o"})
    assert out.data.shape == (8, 1)
    assert sorted(out.labels["row"].values()) == list(range(8))
    assert len(out.labels["row"]) == 8
    print("PASS test_all_positions_preserved")


# ------------------------------------------------------------------ #
# Info follows the new order
# ------------------------------------------------------------------ #

def test_axis_info_follows_order():
    data = np.arange(4).reshape(4, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan,
              "score": [4.0, 3.0, 2.0, 1.0],
              "chrom": ["a", "b", "c", "d"]},
        axis_info={"row": ["score", "chrom"]},
    )
    out, _ = run(form, {
        "dim": "row", "by": "score", "output": "o",
    })
    # Ascending by score: row3 (1), row2 (2), row1 (3), row0 (4)
    assert out.info["chrom"] == ["d", "c", "b", "a"]
    assert out.info["score"] == [1.0, 2.0, 3.0, 4.0]
    print("PASS test_axis_info_follows_order")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_positions_last():
    data = np.arange(5).reshape(5, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan,
              "score": [3.0, np.nan, 1.0, 5.0, np.nan]},
        axis_info={"row": ["score"]},
    )
    out, exp = run(form, {
        "dim": "row", "by": "score", "output": "o",
    })
    # Ascending finite: row2 (1), row0 (3), row3 (5)
    # NaN last: row1, row4 (source order)
    assert out.data.flatten().tolist() == [2.0, 0.0, 3.0, 1.0, 4.0]
    assert exp["n_missing"] == 2
    assert exp["order"][-1]["value"] is None
    print("PASS test_nan_positions_last")


def test_all_nan_raises():
    form = make_form(
        np.arange(3).reshape(3, 1),
        info={"missing_code": np.nan, "score": [np.nan, np.nan, np.nan]},
        axis_info={"row": ["score"]},
    )
    try:
        run(form, {"dim": "row", "by": "score", "output": "o"})
    except StepError as exc:
        assert "no finite" in str(exc)
        print("PASS test_all_nan_raises")
        return
    raise AssertionError("did not raise on all-NaN")


# ------------------------------------------------------------------ #
# Multi-dimensional Form
# ------------------------------------------------------------------ #

def test_reorders_only_target_axis():
    data = np.arange(12).reshape(3, 4)
    form = Form(
        data=data.astype(np.float32),
        dims=["row", "col"],
        labels={
            "row": {"r0": 0, "r1": 1, "r2": 2},
            "col": {f"c{i}": i for i in range(4)},
        },
        info={"missing_code": np.nan, "score": [3.0, 1.0, 2.0]},
        axis_info={"row": ["score"]},
    )
    out, _ = run(form, {"dim": "row", "by": "score", "output": "o"})
    # Ascending: r1 (1), r2 (2), r0 (3)
    assert out.data[0].tolist() == [4.0, 5.0, 6.0, 7.0]
    assert out.data[1].tolist() == [8.0, 9.0, 10.0, 11.0]
    assert out.data[2].tolist() == [0.0, 1.0, 2.0, 3.0]
    assert out.labels["col"] == form.labels["col"]
    print("PASS test_reorders_only_target_axis")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    form = make_form(
        np.arange(5).reshape(5, 1),
        info={"missing_code": np.nan, "score": list(range(5))},
        axis_info={"row": ["score"]},
    )
    bad = [
        {"by": "score", "output": "o"},
        {"dim": "row", "output": "o"},
        {"dim": "nope", "by": "score", "output": "o"},
        {"dim": "row", "by": "missing", "output": "o"},
        {"dim": "row", "by": "col0", "output": "o"},
    ]
    for params in bad:
        try:
            run(form, params)
        except StepError:
            continue
        raise AssertionError(f"params={params} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_ascending_reorders_all,
        test_descending_reorders_all,
        test_all_positions_preserved,
        test_axis_info_follows_order,
        test_nan_positions_last,
        test_all_nan_raises,
        test_reorders_only_target_axis,
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