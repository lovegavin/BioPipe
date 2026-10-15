# tasks/annotate_demo/test_annotate.py
"""Correctness tests for annotate.

Run:
    python tasks/annotate_demo/test_annotate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from src.core import Form, StepError                   # noqa: E402
from src.reader.readers._encoder import LabelEncoder   # noqa: E402
from src.task.step.steps.annotate import AnnotateStep  # noqa: E402


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


def make_form(dims, labels, data, info=None, axis_info=None):
    return Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels={d: dict(v) for d, v in labels.items()},
        info=dict(info or {"missing_code": np.nan}),
        axis_info={k: list(v) for k, v in (axis_info or {}).items()},
    )


def run(target, reference, params):
    ctx = FakeContext(params)
    step = AnnotateStep()
    step.run(ctx, [target, reference])
    return ctx.forms[params.get("output", "annotate")], step.export(ctx)


def _target(labels_by_position, data):
    """Build a target whose key dim label order matches position order."""
    keys = [k for k, _ in sorted(labels_by_position.items(),
                                  key=lambda kv: kv[1])]
    return make_form(
        ["variant", "stat"],
        {"variant": {k: i for i, k in enumerate(keys)},
         "stat": {"beta": 0}},
        data,
    )


def _reference(keys, fields, data, encoders=None):
    info = {"missing_code": np.nan}
    if encoders:
        info["encoders"] = encoders
    return make_form(
        ["variant_id", "field"],
        {"variant_id": {k: i for i, k in enumerate(keys)},
         "field": {f: i for i, f in enumerate(fields)}},
        data,
        info=info,
    )


# ------------------------------------------------------------------ #
# Alignment by label
# ------------------------------------------------------------------ #

def test_full_match_numeric():
    target = _target({"rs1": 0, "rs2": 1}, [[0.5], [0.2]])
    reference = _reference(
        ["rs1", "rs2"], ["AF"],
        [[0.12], [0.05]],
    )
    out, exp = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    assert np.allclose(out.info["AF"], [0.12, 0.05])
    assert out.axis_info["variant"] == ["AF"]
    assert exp["n_matched"] == 2
    assert exp["n_unmatched"] == 0
    print("PASS test_full_match_numeric")


def test_reorders_by_label_not_position():
    target = _target({"rs2": 0, "rs1": 1}, [[0.2], [0.5]])
    reference = _reference(["rs1", "rs2"], ["AF"], [[0.12], [0.05]])
    out, _ = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    # rs2 at target position 0; its AF is 0.05
    assert np.allclose(out.info["AF"], [0.05, 0.12])
    print("PASS test_reorders_by_label_not_position")


def test_missing_keys_become_nan():
    target = _target({"rs1": 0, "rs3": 1}, [[0.5], [0.2]])
    reference = _reference(["rs1", "rs2"], ["AF"], [[0.12], [0.05]])
    out, exp = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    assert np.isclose(out.info["AF"][0], 0.12)
    assert np.isnan(out.info["AF"][1])
    assert exp["n_matched"] == 1
    assert exp["n_unmatched"] == 1
    assert exp["unmatched_labels"] == ["rs3"]
    print("PASS test_missing_keys_become_nan")


# ------------------------------------------------------------------ #
# Multiple fields
# ------------------------------------------------------------------ #

def test_multiple_fields():
    target = _target({"rs1": 0, "rs2": 1}, [[0.5], [0.2]])
    reference = _reference(
        ["rs1", "rs2"], ["gene", "AF", "effect"],
        [[1.0, 0.12, 0.3], [2.0, 0.05, -0.1]],
    )
    out, _ = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["gene", "AF", "effect"],
        "output": "o",
    })
    assert np.allclose(out.info["gene"], [1.0, 2.0])
    assert np.allclose(out.info["AF"], [0.12, 0.05])
    assert np.allclose(out.info["effect"], [0.3, -0.1])
    assert out.axis_info["variant"] == ["AF", "effect", "gene"]
    print("PASS test_multiple_fields")


# ------------------------------------------------------------------ #
# Encoders
# ------------------------------------------------------------------ #

def test_encoder_reused_verbatim():
    enc = LabelEncoder()
    enc.fit_transform(["GENE1", "GENE2"])
    target = _target({"rs1": 0, "rs2": 1}, [[0.5], [0.2]])
    reference = _reference(
        ["rs1", "rs2"], ["gene"],
        [[float(enc.mapping["GENE1"])], [float(enc.mapping["GENE2"])]],
        encoders={"field": {"gene": enc}},
    )
    out, exp = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["gene"],
        "output": "o",
    })
    np.testing.assert_array_equal(out.info["gene"], [0.0, 1.0])
    assert out.info["encoders"]["variant"]["gene"] is enc
    assert exp["encoded_fields"] == ["gene"]
    print("PASS test_encoder_reused_verbatim")


def test_encoder_absent_for_numeric_field():
    target = _target({"rs1": 0}, [[0.5]])
    reference = _reference(["rs1"], ["AF"], [[0.12]])
    out, exp = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    assert "encoders" not in out.info
    assert exp["encoded_fields"] == []
    print("PASS test_encoder_absent_for_numeric_field")


# ------------------------------------------------------------------ #
# Structure preservation
# ------------------------------------------------------------------ #

def test_preserves_target_info_and_axis_info():
    target = make_form(
        ["variant", "stat"],
        {"variant": {"rs1": 0, "rs2": 1}, "stat": {"beta": 0}},
        [[0.5], [0.2]],
        info={"missing_code": np.nan, "chrom": ["1", "2"]},
        axis_info={"variant": ["chrom"]},
    )
    reference = _reference(["rs1", "rs2"], ["AF"], [[0.12], [0.05]])
    out, _ = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    assert out.info["chrom"] == ["1", "2"]
    assert np.allclose(out.info["AF"], [0.12, 0.05])
    assert set(out.axis_info["variant"]) == {"chrom", "AF"}
    assert np.allclose(out.data, target.data)
    print("PASS test_preserves_target_info_and_axis_info")


def test_data_shape_and_labels_unchanged():
    target = _target({"rs1": 0, "rs2": 1}, [[0.5], [0.2]])
    reference = _reference(["rs1", "rs2"], ["AF"], [[0.12], [0.05]])
    out, _ = run(target, reference, {
        "target_dim": "variant",
        "source_dim": "variant_id",
        "fields": ["AF"],
        "output": "o",
    })
    assert out.dims == ["variant", "stat"]
    assert out.data.shape == (2, 1)
    assert out.labels["variant"] == {"rs1": 0, "rs2": 1}
    print("PASS test_data_shape_and_labels_unchanged")


# ------------------------------------------------------------------ #
# Errors
# ------------------------------------------------------------------ #

def test_bad_params_raise():
    target = _target({"rs1": 0}, [[0.5]])
    reference = _reference(["rs1"], ["AF"], [[0.12]])
    bad = [
        {"source_dim": "variant_id", "fields": ["AF"], "output": "o"},
        {"target_dim": "variant", "fields": ["AF"], "output": "o"},
        {"target_dim": "variant", "source_dim": "variant_id",
         "output": "o"},
        {"target_dim": "nope", "source_dim": "variant_id",
         "fields": ["AF"], "output": "o"},
        {"target_dim": "variant", "source_dim": "nope",
         "fields": ["AF"], "output": "o"},
        {"target_dim": "variant", "source_dim": "variant_id",
         "fields": ["missing"], "output": "o"},
    ]
    for params in bad:
        try:
            run(target, reference, params)
        except StepError:
            continue
        raise AssertionError(f"params={params} did not raise")
    print("PASS test_bad_params_raise")


def main():
    tests = [
        test_full_match_numeric,
        test_reorders_by_label_not_position,
        test_missing_keys_become_nan,
        test_multiple_fields,
        test_encoder_reused_verbatim,
        test_encoder_absent_for_numeric_field,
        test_preserves_target_info_and_axis_info,
        test_data_shape_and_labels_unchanged,
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
