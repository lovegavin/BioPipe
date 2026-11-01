"""Tests for the ESM-IF position-entropy operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import pick_reader
from src.task.step.steps.esm_if_position_entropy import (
    EsmIfPositionEntropyStep,
    design_counts,
    position_rows,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"
CHECKPOINT = Path("/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form():
    reader = pick_reader(FIXTURE).implementation()
    return reader.read(
        FIXTURE,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def _run(params):
    step = EsmIfPositionEntropyStep()
    ctx = Ctx(params)
    step.run(ctx, [_form()])
    return step, ctx


def _entropy_available() -> bool:
    if not CHECKPOINT.is_file():
        return False
    try:
        import biotite.structure as structure

        if not hasattr(structure, "filter_backbone"):
            structure.filter_backbone = structure.filter_peptide_backbone
        import esm  # noqa: F401
        import torch  # noqa: F401
        import torch_scatter  # noqa: F401
        return True
    except Exception:
        return False


def test_design_counts_hand_values() -> None:
    counts = design_counts(["AAAA", "ACAA"], 4)
    assert counts.shape == (4, 20)
    assert counts[0].sum() == 2
    rows = position_rows(counts, "AAAA")
    assert rows[0][0] == pytest.approx(0.0)
    assert rows[1][0] == pytest.approx(1.0)
    assert rows[1][1] == pytest.approx(0.5)
    assert rows[1][2] == pytest.approx(0.5)


def test_design_counts_rejects_bad_input() -> None:
    with pytest.raises(StepError, match="at least one design"):
        design_counts([], 4)
    with pytest.raises(StepError, match="does not match"):
        design_counts(["AAAA"], 5)
    with pytest.raises(StepError, match="non-standard residue"):
        design_counts(["AAXA"], 4)


@pytest.mark.parametrize(
    "params, message",
    [
        ({"model_path": str(CHECKPOINT), "num_samples": 1}, "num_samples"),
        ({"model_path": str(CHECKPOINT), "temperature": 0.0}, "temperature"),
        ({"model_path": str(CHECKPOINT), "seed": -3}, "seed"),
        ({"model_path": "/tmp/does-not-exist.pt", "chain": "C"}, "not a file"),
    ],
)
def test_parameter_errors(params, message: str) -> None:
    with pytest.raises(StepError, match=message):
        _run(params)


def test_wrong_dims() -> None:
    form = _form()
    two = form.__class__(
        data=form.data,
        dims=["atom", "other"],
        labels={"atom": form.labels["atom"], "other": {name: index for index, name in enumerate(form.labels["field"])}},
        info={"missing_code": np.nan},
    )
    step = EsmIfPositionEntropyStep()
    with pytest.raises(StepError, match="expected a structure form"):
        step.run(Ctx({"model_path": str(CHECKPOINT)}), [two])


@pytest.mark.skipif(not _entropy_available(), reason="ESM-IF checkpoint or deps missing")
def test_real_checkpoint_entropy() -> None:
    step, ctx = _run(
        {
            "model_path": str(CHECKPOINT),
            "chain": "C",
            "num_samples": 4,
            "temperature": 0.1,
            "seed": 1,
        }
    )
    out = ctx["out"]
    assert list(out.dims) == ["position", "statistic"]
    assert out.data.shape == (16, 3)
    assert list(out.labels["statistic"]) == [
        "entropy_bits",
        "recovery",
        "max_frequency",
    ]
    assert (out.data[:, 0] >= 0).all()
    assert 0.0 <= out.data[:, 1].max() <= 1.0
    assert len(out.info["consensus"]) == 16
    assert len(out.info["sequences"]) == 4
    exported = step.export(ctx)
    assert exported["num_samples"] == 4
    assert exported["most_variable"]
