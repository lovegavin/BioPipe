# tasks/prioritize_demo/test_prioritize.py
"""Correctness tests for prioritize.

Run:
    python tasks/prioritize_demo/test_prioritize.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                       # noqa: E402
from src.reader.readers._encoder import LabelEncoder       # noqa: E402
from src.task.step.steps.prioritize import PrioritizeStep  # noqa: E402


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
    step = PrioritizeStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "prioritize")], step.export(ctx)


# ------------------------------------------------------------------ #
# Ranking direction
# ------------------------------------------------------------------ #

def test_descending_keeps_largest():
    data = np.arange(10).reshape(10, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": list(range(10))},
        axis_info={"row": ["score"]},
    )
    out, exp = run(form, {
        "dim": "row", "by": "score", "top_n": 3, "output": "o",
    })
    assert out.data.flatten().tolist() == [7.0, 8.0, 9.0]
    assert exp["ranking"][0]["label"] == "row9"
    assert exp["ranking"][0]["rank"] == 1
    print("PASS test_descending_keeps_largest")


def test_ascending_keeps_smallest():
    data = np.arange(10).reshape(10, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": list(range(10))},
        axis_info={"row": ["score"]},
    )
    out, exp = run(form, {
        "dim": "row", "by": "score", "top_n": 3,
        "ascending": True, "output": "o",
    })
    assert out.data.flatten().tolist() == [0.0, 1.0, 2.0]
    assert exp["ranking"][0]["label"] == "row0"
    print("PASS test_ascending_keeps_smallest")


# ------------------------------------------------------------------ #
# Source order in output
# ------------------------------------------------------------------ #

def test_source_order_in_output():
    data = np.array([[30.0], [10.0], [50.0], [20.0], [40.0]])
    form = make_form(
        data,
        info={"missing_code": np.nan, "score": [30, 10, 50, 20, 40]},
        axis_info={"row": ["score"]},
    )
    out, _ = run(form, {
        "dim": "row", "by": "score", "top_n": 3, "output": "o",
    })
    # Top 3 by score: row2 (50), row4 (40), row0 (30)
    # Source order: row0, row2, row4
    assert out.data.flatten().tolist() == [30.0, 50.0, 40.0]
    assert out.labels["row"] == {"row0": 0, "row2": 1, "row4": 2}
    print("PASS test_source_order_in_output")


# ------------------------------------------------------------------ #
# NaN handling
# ------------------------------------------------------------------ #

def test_nan_ranked_last():
    data = np.arange(5).reshape(5, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan,
              "score": [3.0, np.nan, 1.0, 5.0, np.nan]},
        axis_info={"row": ["score"]},
    )
    out, exp = run(form, {
        "dim": "row", "by": "score", "top_n": 3, "output": "o",
    })
    # Finite values: row3 (5), row0 (3), row2 (1)
    # NaN: row1, row4
    assert out.data.flatten().tolist() == [0.0, 2.0, 3.0]
    assert exp["ranking"][0]["label"] == "row3"
    print("PASS test_nan_ranked_last")


def test_all_nan_raises():
    form = make_form(
        np.arange(3).reshape(3, 1),
        info={"missing_code": np.nan, "score": [np.nan, np.nan, np.nan]},
        axis_info={"row": ["score"]},
    )
    try:
        run(form, {"dim": "row", "by": "score", "top_n": 2, "output": "o"})
    except StepError as exc:
        assert "no finite" in str(exc)
        print("PASS test_all_nan_raises")
        return
    raise AssertionError("did not raise on all-NaN")


# ------------------------------------------------------------------ #
# Info preservation
# ------------------------------------------------------------------ #

def test_other_info_preserved():
    data = np.arange(5).reshape(5, 1)
    form = make_form(
        data,
        info={"missing_code": np.nan,
              "score": [3.0, 1.0, 4.0, 2.0, 5.0],
              "chrom": ["1", "2", "3", "4", "5"]},
        axis_info={"row": ["score", "chrom"]},
    )
    out, _ = run(form, {
        "dim": "row", "by": "score", "top_n": 2, "output": "o",
    })
    # Kept: row4 (5), row2 (4). Source order: row2, row4
    assert out.info["chrom"] == ["3", "5"]
    assert out.info["score"] == [4.0, 5.0]
    print("PASS test_other_info_preserved")


def test_encoded_field_rejected():
    enc = LabelEncoder()
    enc.fit_transform(["A", "B", "C"])
    form = make_form(
        np.arange(3).reshape(3, 1),
        info={"missing_code": np.nan,
              "score": [0.0, 1.0, 2.0],
              "encoders": {"row": {"category": enc}}},
        axis_info={"row": ["score", "category"]},
    )
    try:
        run(form, {"dim": "row", "by": "category",
                   "top_n": 2, "output": "o"})
    except StepError as exc:
        assert "encoded" in str(exc)
        print("PASS test_encoded_field_rejected")
        return
    raise AssertionError("did not reject encoded field")


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
        {"by": "score", "top_n": 2, "output": "o"},
        {"dim": "row", "top_n": 2, "output": "o"},
        {"dim": "row", "by": "score", "output": "o"},
        {"dim": "nope", "by": "score", "top_n": 2, "output": "o"},
        {"dim": "row", "by": "missing", "top_n": 2, "output": "o"},
        {"dim": "row", "by": "score", "top_n": 0, "output": "o"},
        {"dim": "row", "by": "score", "top_n": 99, "output": "o"},
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
        test_descending_keeps_largest,
        test_ascending_keeps_smallest,
        test_source_order_in_output,
        test_nan_ranked_last,
        test_all_nan_raises,
        test_other_info_preserved,
        test_encoded_field_rejected,
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