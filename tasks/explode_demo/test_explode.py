# tasks/explode_demo/test_explode.py
"""Correctness tests for explode.

Run:
    python tasks/explode_demo/test_explode.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                     # noqa: E402
from src.task.step.steps.explode import ExplodeStep      # noqa: E402


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


def make_form(data, info, axis_info, dims=("row", "col")):
    data = np.asarray(data, dtype=np.float32)
    labels = {}
    for i, d in enumerate(dims):
        labels[d] = {f"{d}{j}": j for j in range(data.shape[i])}
    return Form(
        data=data,
        dims=list(dims),
        labels=labels,
        info=dict(info),
        axis_info={k: list(v) for k, v in axis_info.items()},
    )


def run(form, params):
    ctx = FakeContext(params)
    step = ExplodeStep()
    step.run(ctx, [form])
    return ctx.forms[params.get("output", "explode")], step.export(ctx)


def test_basic_explosion():
    form = make_form(
        [[1.0], [2.0], [3.0]],
        {"missing_code": np.nan,
         "go": ["GO:1;GO:2", "GO:3", "GO:4;GO:5;GO:6"]},
        {"row": ["go"]},
    )
    out, exp = run(form, {
        "dim": "row", "field": "go", "output": "o",
    })
    assert out.data.shape == (6, 1)
    assert out.data.flatten().tolist() == [1, 1, 2, 3, 3, 3]
    assert len(out.labels["row"]) == 6
    assert exp["n_before"] == 3
    assert exp["n_after"] == 6
    assert "go" not in out.info
    assert "go" not in out.axis_info.get("row", [])
    print("PASS test_basic_explosion")


def test_other_info_replicated():
    form = make_form(
        [[1.0], [2.0]],
        {"missing_code": np.nan,
         "go": ["A;B", "C"],
         "chrom": ["1", "2"]},
        {"row": ["go", "chrom"]},
    )
    out, _ = run(form, {"dim": "row", "field": "go", "output": "o"})
    assert out.info["chrom"] == ["1", "1", "2"]
    assert out.axis_info["row"] == ["chrom"]
    print("PASS test_other_info_replicated")


def test_keep_empty():
    form = make_form(
        [[1.0], [2.0]],
        {"missing_code": np.nan, "go": ["A;B", ""]},
        {"row": ["go"]},
    )
    out, exp = run(form, {
        "dim": "row", "field": "go",
        "keep_empty": True, "output": "o",
    })
    assert exp["n_after"] == 3
    print("PASS test_keep_empty")


def test_drop_empty():
    form = make_form(
        [[1.0], [2.0]],
        {"missing_code": np.nan, "go": ["A;B", ""]},
        {"row": ["go"]},
    )
    out, exp = run(form, {"dim": "row", "field": "go", "output": "o"})
    assert exp["n_after"] == 2
    print("PASS test_drop_empty")


def test_list_input():
    form = make_form(
        [[1.0]],
        {"missing_code": np.nan, "go": [["A", "B"]]},
        {"row": ["go"]},
    )
    out, exp = run(form, {"dim": "row", "field": "go", "output": "o"})
    assert exp["n_after"] == 2
    print("PASS test_list_input")


def test_bad_params_raise():
    form = make_form(
        [[1.0]],
        {"missing_code": np.nan, "go": ["A"]},
        {"row": ["go"]},
    )
    bad = [
        {"field": "go", "output": "o"},
        {"dim": "row", "output": "o"},
        {"dim": "nope", "field": "go", "output": "o"},
        {"dim": "row", "field": "missing", "output": "o"},
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
        test_basic_explosion,
        test_other_info_replicated,
        test_keep_empty,
        test_drop_empty,
        test_list_input,
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