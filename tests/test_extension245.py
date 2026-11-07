"""Tests for the ESMFold wrapper operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps import esmfold_predict as esmfold_module
from src.task.step.steps.esmfold_predict import EsmfoldPredictStep

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "tests" / "fixtures" / "backbone_1bc8_c60_75.pdb"
SEQUENCE = "ACDEFGHIK"


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = dict(params or {})
        self.metadata = {}


class FakeModel:
    def __init__(self, text: str):
        self.text = text
        self.calls = []

    def infer_pdb(self, sequence, **kwargs):
        self.calls.append(sequence)
        return self.text


def _fake_loader(text: str, monkeypatch):
    model = FakeModel(text)

    def loader(device, chunk_size, weights_dir=""):
        return model

    monkeypatch.setattr(esmfold_module, "_load_model", loader)
    return model


def test_prediction_reads_the_returned_pdb(monkeypatch) -> None:
    _fake_loader(FIXTURE.read_text(encoding="utf-8"), monkeypatch)
    ctx = Ctx({"output": "structure"})
    EsmfoldPredictStep().run(ctx, [encode_sequences([SEQUENCE], "sequence", "position", "protein")])
    out = ctx["structure"]
    assert out.dims == ["atom", "field"]
    values = out.data[:, out.labels["field"]["bfactor"]].astype(np.float64)
    assert out.info["mean_plddt"] == pytest.approx(float(values.mean()), rel=1e-6)
    assert out.info["sequence"] == SEQUENCE
    assert out.info["model"] == "esmfold_3B_v1"
    assert out.info["num_recycles"] == 4


def test_only_one_sequence_is_supported(monkeypatch) -> None:
    _fake_loader(FIXTURE.read_text(encoding="utf-8"), monkeypatch)
    with pytest.raises(StepError, match="exactly one sequence"):
        EsmfoldPredictStep().run(
            Ctx(), [encode_sequences(["ACD", "EFG"], "sequence", "position", "protein")]
        )


def test_invalid_device_and_recycles(monkeypatch) -> None:
    _fake_loader(FIXTURE.read_text(encoding="utf-8"), monkeypatch)
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    with pytest.raises(StepError, match="device must be"):
        EsmfoldPredictStep().run(Ctx({"device": "tpu"}), [form])
    with pytest.raises(StepError, match="num_recycles"):
        EsmfoldPredictStep().run(Ctx({"num_recycles": 0}), [form])


def test_empty_sequence_is_rejected(monkeypatch) -> None:
    _fake_loader(FIXTURE.read_text(encoding="utf-8"), monkeypatch)
    empty = encode_sequences([""], "sequence", "position", "protein")
    with pytest.raises(StepError, match="empty"):
        EsmfoldPredictStep().run(Ctx(), [empty])


def test_model_output_without_atoms_is_rejected(monkeypatch) -> None:
    _fake_loader("REMARK no coordinates\n", monkeypatch)
    form = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    with pytest.raises(StepError, match="no atom records"):
        EsmfoldPredictStep().run(Ctx(), [form])


def test_missing_fair_esm_is_reported(monkeypatch) -> None:
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "esm":
            raise ImportError("no esm")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(StepError, match="fair-esm"):
        esmfold_module._load_model("cpu", 64)


def test_runner_round_trip(tmp_path, monkeypatch) -> None:
    _fake_loader(FIXTURE.read_text(encoding="utf-8"), monkeypatch)
    ctx = Context(str(tmp_path / "esmfold"), {"params": {}})
    ctx["sequence"] = encode_sequences([SEQUENCE], "sequence", "position", "protein")
    run(
        ctx,
        [
            {
                "name": "esmfold_predict",
                "inputs": ["sequence"],
                "params": {"output": "structure"},
            }
        ],
    )
    assert ctx["structure"].info["model"] == "esmfold_3B_v1"
    assert list((tmp_path / "esmfold").rglob("*esmfold_predict*.json"))
    assert np.isfinite(ctx["structure"].info["mean_plddt"])



def test_real_esmfold():
    import os

    if os.environ.get("OPERON_ESMFOLD_REAL") != "1":
        pytest.skip("set OPERON_ESMFOLD_REAL=1 to run ESMFold 3B")
    pytest.importorskip("esm")
    from src.task.step.steps._sequence_common import encode_sequences

    ctx = Context(str(Path(__file__).resolve().parent / "_esmfold_real"), {"params": {}})
    ctx["sequence"] = encode_sequences(["MKVLAAGIVGLLLA"], "sequence", "position", "protein")
    run(ctx, [{"name": "esmfold_predict", "inputs": ["sequence"], "params": {"output": "structure", "device": "cpu", "num_recycles": 2}}])
    result = ctx["structure"]
    assert result.data.shape[0] > 50
    fields = result.labels["field"]
    plddt = result.data[:, fields["bfactor"]]
    assert 40.0 < float(plddt.mean()) < 95.0
