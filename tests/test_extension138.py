"""Tests for the official ESM-IF1 inverse-folding operators."""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader import pick_reader, read_source
from src.task.step.steps.esm_if_design import EsmIfDesignStep
from src.task.step.steps.esm_if_score import EsmIfScoreStep

CHECKPOINT = os.environ.get(
    "OPERON_ESM_IF_CHECKPOINT", "/home/gavin/models/esm_if1_gvp4_t16_142M_UR50.pt"
)
FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


def _available() -> bool:
    if not Path(CHECKPOINT).is_file() or not FIXTURE.is_file():
        return False
    try:
        import biotite.structure as biotite_structure
        import torch_scatter  # noqa: F401
        if not hasattr(biotite_structure, "filter_backbone"):
            biotite_structure.filter_backbone = biotite_structure.filter_peptide_backbone
        import esm.inverse_folding  # noqa: F401
    except Exception:  # noqa: BLE001 - optional heavy dependencies
        return False
    return True


pytestmark = pytest.mark.skipif(not _available(), reason="ESM-IF checkpoint or dependencies missing")


class Ctx(dict):
    def __init__(self, params):
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(path=FIXTURE, model=0):
    reader = pick_reader(path).implementation()
    return read_source(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
        reader_id=reader.name,
        model=model,
    )


def test_design_is_reproducible():
    step = EsmIfDesignStep()
    params = {
        "model_path": CHECKPOINT,
        "chain": "C",
        "num_samples": 2,
        "temperature": 0.1,
        "seed": 1,
    }
    ctx = Ctx(params)
    step.run(ctx, [_form()])
    out = ctx["out"]
    first = out.info["sequences"]
    assert list(out.dims) == ["sample", "statistic"]
    assert len(first) == 2
    assert all(len(sequence) == 16 for sequence in first)
    assert all(set(sequence) <= set("ACDEFGHIKLMNPQRSTVWY") for sequence in first)
    assert np.isfinite(out.data[:, 0]).all()
    assert ((out.data[:, 1] >= 0.0) & (out.data[:, 1] <= 1.0)).all()

    second = Ctx(params)
    EsmIfDesignStep().run(second, [_form()])
    assert second["out"].info["sequences"] == first


def test_score_matches_official_mean():
    from esm.inverse_folding.util import load_coords, score_sequence

    from src.task.step.steps._esm_if_common import load_esm_if

    model, alphabet, _torch = load_esm_if(CHECKPOINT, "esm_if_score")
    coords, sequence = load_coords(str(FIXTURE), "C")
    _full, with_coords = score_sequence(model, alphabet, coords, sequence)

    step = EsmIfScoreStep()
    ctx = Ctx({"model_path": CHECKPOINT, "chain": "C"})
    form = _form()
    step.run(ctx, [form])
    out = ctx["out"]
    assert list(out.dims) == ["residue", "statistic"]
    assert len(out.data) == len(sequence)
    assert out.info["sequence"] == sequence
    assert out.info["mean_log_prob"] == pytest.approx(float(with_coords), rel=1e-5, abs=1e-5)
    assert out.info["total_log_prob"] == pytest.approx(float(with_coords) * len(sequence), rel=1e-5)


def test_score_custom_sequence_is_loaded():
    step = EsmIfScoreStep()
    ctx = Ctx({"model_path": CHECKPOINT, "chain": "C", "sequence": "A" * 16})
    step.run(ctx, [_form()])
    assert ctx["out"].info["sequence"] == "A" * 16
    assert np.isfinite(ctx["out"].data).all()


def test_runner_level_contract():
    from src.task.context.base import Context
    from src.task.runner import run

    task_dir = Path(os.environ.get("PYTEST_TMPDIR", "/tmp")) / "esm_if_runner"
    task_dir.mkdir(parents=True, exist_ok=True)
    context = Context(task_dir, {"params": {}})
    context["structure"] = _form()
    run(
        context,
        [
            {
                "name": "esm_if_score",
                "inputs": ["structure"],
                "params": {
                    "model_path": CHECKPOINT,
                    "chain": "C",
                    "output": "scores",
                },
            }
        ],
    )
    assert context["scores"].data.shape == (16, 1)


def test_parameter_errors():
    form = _form()
    with pytest.raises(StepError, match="model_path"):
        step = EsmIfDesignStep()
        step.run(Ctx({"chain": "C"}), [form])
    with pytest.raises(StepError, match="num_samples"):
        step = EsmIfDesignStep()
        step.run(Ctx({"model_path": CHECKPOINT, "chain": "C", "num_samples": 0}), [form])
    with pytest.raises(StepError, match="temperature"):
        step = EsmIfDesignStep()
        step.run(Ctx({"model_path": CHECKPOINT, "chain": "C", "temperature": 0.0}), [form])
    with pytest.raises(StepError, match="chain"):
        step = EsmIfScoreStep()
        step.run(Ctx({"model_path": CHECKPOINT, "chain": "Z"}), [form])
    with pytest.raises(StepError, match="does not match"):
        step = EsmIfScoreStep()
        step.run(Ctx({"model_path": CHECKPOINT, "chain": "C", "sequence": "ACD"}), [form])
    with pytest.raises(StepError, match="not a file"):
        step = EsmIfScoreStep()
        step.run(Ctx({"model_path": "/nonexistent/model.pt", "chain": "C"}), [form])


def test_dims_errors():
    form = Form(
        data=np.zeros((3, 3), np.float32),
        dims=["atom", "coordinate"],
        labels={"atom": {"a": 0, "b": 1, "c": 2}, "coordinate": {"x": 0, "y": 1, "z": 2}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="dims"):
        EsmIfScoreStep().run(Ctx({"model_path": CHECKPOINT}), [form])
