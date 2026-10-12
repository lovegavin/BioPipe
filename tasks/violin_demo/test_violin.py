# tasks/violin_demo/test_violin.py
"""Correctness tests for violin.

Run:
    python tasks/violin_demo/test_violin.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                  # noqa: E402
from src.reader.readers._encoder import LabelEncoder  # noqa: E402
from src.task.step.steps.violin import ViolinStep     # noqa: E402


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


def make_data_form(values_by_sample, value_label="value"):
    samples = list(values_by_sample.keys())
    data = np.array(
        [[values_by_sample[s] for s in samples]], dtype=np.float32
    )
    return Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {value_label: 0},
            "sample": {s: i for i, s in enumerate(samples)},
        },
        info={"missing_code": np.nan},
    )


def make_data_form_multi(values_by_row, row_names, samples):
    data = np.asarray(values_by_row, dtype=np.float32)
    return Form(
        data=data,
        dims=["feature", "sample"],
        labels={
            "feature": {n: i for i, n in enumerate(row_names)},
            "sample": {s: i for i, s in enumerate(samples)},
        },
        info={"missing_code": np.nan},
    )


def make_meta_form(groups_by_sample, group_label="group",
                   use_encoder=False):
    samples = list(groups_by_sample.keys())
    raw = [groups_by_sample[s] for s in samples]
    if use_encoder:
        enc = LabelEncoder()
        enc.fit_transform(raw)
        codes = enc.fit_transform(raw).astype(np.float32)
        info = {
            "missing_code": np.nan,
            "encoders": {"feature": {group_label: enc}},
        }
    else:
        codes = np.asarray(raw, dtype=np.float32)
        info = {"missing_code": np.nan}
    data = codes.reshape(-1, 1)
    return Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {s: i for i, s in enumerate(samples)},
            "feature": {group_label: 0},
        },
        info=info,
    )


def run(data_form, meta_form, params,
        tmp_dir="tasks/violin_demo/output"):
    ctx = FakeContext(params, tmp_dir)
    step = ViolinStep()
    step.run(ctx, [data_form, meta_form])
    return step.export(ctx)


# ------------------------------------------------------------------ #
# Summary statistics
# ------------------------------------------------------------------ #

def test_two_groups_summary():
    values = {"s0": 1.0, "s1": 2.0, "s2": 3.0,
              "s3": 10.0, "s4": 11.0, "s5": 12.0}
    groups = {"s0": 0, "s1": 0, "s2": 0,
              "s3": 1, "s4": 1, "s5": 1}
    data = make_data_form(values)
    meta = make_meta_form(groups)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    assert exp["n_groups"] == 2
    assert exp["groups"] == ["0", "1"]
    g0 = exp["summary"]["0"]
    g1 = exp["summary"]["1"]
    assert g0["n"] == 3
    assert g0["median"] == 2.0
    assert g0["mean"] == 2.0
    assert g1["median"] == 11.0
    assert g1["mean"] == 11.0
    print("PASS test_two_groups_summary")


def test_quartiles():
    values = {"s0": 1.0, "s1": 2.0, "s2": 3.0, "s3": 4.0}
    groups = {"s0": "A", "s1": "A", "s2": "A", "s3": "A"}
    data = make_data_form(values)
    meta = make_meta_form(groups, use_encoder=True)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    gA = exp["summary"]["A"]
    # numpy linear interpolation: q25 = 1.75, q50 = 2.5, q75 = 3.25
    assert abs(gA["q25"] - 1.75) < 1e-6
    assert abs(gA["median"] - 2.5) < 1e-6
    assert abs(gA["q75"] - 3.25) < 1e-6
    print("PASS test_quartiles")


def test_groups_arg_orders():
    values = {"s0": 1.0, "s1": 2.0, "s2": 10.0, "s3": 20.0}
    groups = {"s0": "B", "s1": "B", "s2": "A", "s3": "A"}
    data = make_data_form(values)
    meta = make_meta_form(groups, use_encoder=True)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "groups": ["A", "B"],
        "filename": "t.png",
    })
    assert exp["groups"] == ["A", "B"]
    assert exp["summary"]["A"]["median"] == 15.0
    assert exp["summary"]["B"]["median"] == 1.5
    print("PASS test_groups_arg_orders")


def test_missing_group_raises():
    values = {"s0": 1.0, "s1": 2.0}
    groups = {"s0": "A", "s1": "B"}
    data = make_data_form(values)
    meta = make_meta_form(groups, use_encoder=True)
    try:
        run(data, meta, {
            "dim": "feature", "value_label": "value",
            "group_dim": "sample", "group_label": "group",
            "groups": ["A", "C"],
            "filename": "t.png",
        })
    except StepError as exc:
        assert "C" in str(exc)
        print("PASS test_missing_group_raises")
        return
    raise AssertionError("did not raise on missing group")


# ------------------------------------------------------------------ #
# NaN and alignment
# ------------------------------------------------------------------ #

def test_nan_skipped():
    values = {"s0": 1.0, "s1": np.nan, "s2": 3.0,
              "s3": 10.0, "s4": 11.0, "s5": 12.0}
    groups = {"s0": 0, "s1": 0, "s2": 0,
              "s3": 1, "s4": 1, "s5": 1}
    data = make_data_form(values)
    meta = make_meta_form(groups)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    assert exp["summary"]["0"]["n"] == 2
    assert exp["summary"]["1"]["n"] == 3
    print("PASS test_nan_skipped")


def test_sample_alignment_by_label():
    values = {"s0": 1.0, "s1": 2.0, "s2": 3.0,
              "s3": 10.0, "s4": 11.0, "s5": 12.0, "extra": 99.0}
    groups = {"s0": 0, "s1": 0, "s2": 0,
              "s3": 1, "s4": 1, "s5": 1}
    data = make_data_form(values)
    meta = make_meta_form(groups)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    assert exp["n_samples"] == 6
    print("PASS test_sample_alignment_by_label")


def test_multiple_value_columns():
    samples = [f"s{i}" for i in range(4)]
    data = make_data_form_multi(
        [[1.0, 2.0, 3.0, 4.0],
         [10.0, 20.0, 30.0, 40.0]],
        ["colA", "colB"],
        samples,
    )
    groups = {f"s{i}": i % 2 for i in range(4)}
    meta = make_meta_form(groups)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "colB",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    # Group 0 = {s0, s2}: colB = [10, 30], median = 20
    # Group 1 = {s1, s3}: colB = [20, 40], median = 30
    assert exp["summary"]["0"]["median"] == 20.0
    assert exp["summary"]["1"]["median"] == 30.0
    print("PASS test_multiple_value_columns")


# ------------------------------------------------------------------ #
# Inner modes
# ------------------------------------------------------------------ #

def test_inner_modes_accepted():
    values = {"s0": 1.0, "s1": 2.0, "s2": 3.0,
              "s3": 4.0, "s4": 5.0, "s5": 6.0}
    groups = {"s0": 0, "s1": 0, "s2": 0,
              "s3": 1, "s4": 1, "s5": 1}
    data = make_data_form(values)
    meta = make_meta_form(groups)
    for mode in ("box", "quartile", "point", "none"):
        exp = run(data, meta, {
            "dim": "feature", "value_label": "value",
            "group_dim": "sample", "group_label": "group",
            "inner": mode, "filename": f"t_{mode}.png",
        })
        assert exp["inner"] == mode
    print("PASS test_inner_modes_accepted")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    values = {"s0": 1.0, "s1": 2.0}
    groups = {"s0": 0, "s1": 1}
    data = make_data_form(values)
    meta = make_meta_form(groups)

    for bad in (
        {"dim": "feature", "group_dim": "sample",
         "group_label": "group", "filename": "t.png"},       # no value_label
        {"dim": "feature", "value_label": "value",
         "group_label": "group", "filename": "t.png"},        # no group_dim
        {"dim": "feature", "value_label": "value",
         "group_dim": "sample", "filename": "t.png"},          # no group_label
        {"dim": "feature", "value_label": "value",
         "group_dim": "sample", "group_label": "group"},       # no filename
        {"dim": "feature", "value_label": "nonexistent",
         "group_dim": "sample", "group_label": "group",
         "filename": "t.png"},                                  # bad value
        {"dim": "feature", "value_label": "value",
         "group_dim": "sample", "group_label": "nonexistent",
         "filename": "t.png"},                                  # bad group
        {"dim": "feature", "value_label": "value",
         "group_dim": "sample", "group_label": "group",
         "filename": "t.png", "inner": "bogus"},
    ):
        try:
            run(data, meta, bad)
        except StepError:
            continue
        raise AssertionError(f"params={bad} did not raise")
    print("PASS test_bad_params_raise")


def test_single_group_ok():
    """A single group still produces a valid violin."""
    values = {"s0": 1.0, "s1": 2.0, "s2": 3.0}
    groups = {"s0": "A", "s1": "A", "s2": "A"}
    data = make_data_form(values)
    meta = make_meta_form(groups, use_encoder=True)
    exp = run(data, meta, {
        "dim": "feature", "value_label": "value",
        "group_dim": "sample", "group_label": "group",
        "filename": "t.png",
    })
    assert exp["n_groups"] == 1
    assert exp["summary"]["A"]["n"] == 3
    print("PASS test_single_group_ok")


def main():
    tests = [
        test_two_groups_summary,
        test_quartiles,
        test_groups_arg_orders,
        test_missing_group_raises,
        test_nan_skipped,
        test_sample_alignment_by_label,
        test_multiple_value_columns,
        test_inner_modes_accepted,
        test_bad_params_raise,
        test_single_group_ok,
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