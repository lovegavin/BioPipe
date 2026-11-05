"""Extension tests for the ESM-IF partial redesign operator."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.esm_if_redesign import _fixed_partial, designed_recovery

STEP = pytest.importorskip("src.task.step.steps.esm_if_redesign").EsmIfRedesignStep
FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
CHECKPOINT = os.environ.get("BIOPIPE_ESM_IF_CHECKPOINT", "/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _structure_form():
    from src.reader import read_source

    return read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def _run(params):
    step = STEP()
    ctx = Ctx(params)
    step.run(ctx, [_structure_form()])
    return ctx["out"], step.export(ctx)


def test_fixed_partial_masks_design_positions():
    assert _fixed_partial("SRAL", [0, 1]) == ["<mask>", "<mask>", "A", "L"]
    assert _fixed_partial("SRAL", []) == ["S", "R", "A", "L"]


def test_designed_recovery():
    assert designed_recovery("SRAL", "ARAL", [0, 1]) == 0.5
    assert designed_recovery("SRAL", "SRAL", [0, 1]) == 1.0
    assert designed_recovery("SRAL", "AAAA", [0, 1]) == 0.0


def _require_checkpoint():
    if not Path(CHECKPOINT).is_file():
        pytest.skip("ESM-IF checkpoint is not available")
    pytest.importorskip("biotite")
    esm = pytest.importorskip("esm")
    if not hasattr(esm, "pretrained"):
        pytest.skip("fair-esm is shadowed by the ESM-3 package")
    try:
        pytest.importorskip("torch_scatter")
    except OSError as exc:
        pytest.skip(f"torch_scatter is ABI-incompatible: {exc}")


def test_real_partial_redesign_keeps_fixed_context():
    _require_checkpoint()
    out, export = _run(
        {
            "chain": "C",
            "model_path": CHECKPOINT,
            "design_positions": "1,2",
            "num_samples": 2,
            "temperature": 0.1,
            "seed": 1,
        }
    )
    assert out.data.shape == (2, 3)
    assert out.info["design_positions"] == [1, 2]
    assert out.info["fixed_positions"] == list(range(3, 17))
    native = out.info["native_sequence"]
    assert native == "SRALRYYYVKNIIKKV"
    for sequence in out.info["sequences"]:
        assert len(sequence) == 16
        assert sequence[2:] == native[2:]
    np.testing.assert_allclose(out.data[:, 1], [0.0, 0.0], atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], [2.0, 2.0])
    assert out.data[0, 0] == pytest.approx(-2.6846, abs=1e-3)


def test_full_redesign_without_fixed_positions():
    _require_checkpoint()
    out, _ = _run(
        {
            "chain": "C",
            "model_path": CHECKPOINT,
            "num_samples": 1,
            "temperature": 0.1,
            "seed": 3,
        }
    )
    assert out.info["fixed_positions"] == []
    assert out.info["design_positions"] == list(range(1, 17))
    assert len(out.info["sequences"][0]) == 16


def test_parameter_errors():
    params = {"chain": "C", "model_path": "/tmp/does-not-exist.pt"}
    for overrides, message in [
        ({"temperature": 5.0}, "temperature"),
        ({"num_samples": 0}, "num_samples"),
        ({"seed": -1}, "seed must not be negative"),
        ({"model_path": ""}, "model_path"),
        ({"design_positions": "99"}, "outside the chain"),
        ({"chain": "Z"}, "was not found in the structure form"),
    ]:
        with pytest.raises(StepError, match=message):
            _run({**params, **overrides})


def test_rejects_wrong_dims():
    step = STEP()
    ctx = Ctx({"chain": "C", "model_path": "/tmp/x.pt", "output": "out"})
    from src.core.forms.form import Form

    with pytest.raises(StepError, match="structure form with dims"):
        step.run(ctx, [Form(data=np.zeros((2, 2), dtype=np.float32), dims=["atom", "x"], labels={})])
