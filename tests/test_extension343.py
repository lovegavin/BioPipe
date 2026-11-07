"""esm3_secondary_structure: track mapping, summary and runner contract."""

import types

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import esm3_secondary_structure as module
from src.task.step.steps.esm3_secondary_structure import (
    clean_structure,
    predict_secondary_structure,
    ss_summary,
    state_code,
)
from src.task.step.steps._sequence_common import encode_sequences


def _install_esm_stub(monkeypatch):
    """Register minimal esm modules so generation works without the package."""

    esm = types.ModuleType("esm")
    sdk = types.ModuleType("esm.sdk")
    api = types.ModuleType("esm.sdk.api")

    class ESMProtein:
        def __init__(self, sequence=None, **kwargs):
            self.sequence = sequence

    class GenerationConfig:
        def __init__(self, track="sequence", num_steps=None, **kwargs):
            self.track = track
            self.num_steps = num_steps

    api.ESMProtein = ESMProtein
    api.GenerationConfig = GenerationConfig
    sdk.api = api
    esm.sdk = sdk
    monkeypatch.setitem(__import__("sys").modules, "esm", esm)
    monkeypatch.setitem(__import__("sys").modules, "esm.sdk", sdk)
    monkeypatch.setitem(__import__("sys").modules, "esm.sdk.api", api)


def test_state_codes_and_summary():
    assert [state_code(c) for c in "HGBEITS "] == [0, 0, 1, 1, 0, 2, 2, 2]
    summary = ss_summary("HHHEE")
    assert summary["n_helix"] == 3 and summary["n_strand"] == 2 and summary["n_coil"] == 0
    assert summary["helix_fraction"] == pytest.approx(0.6)


def test_clean_structure_pads_and_truncates():
    assert clean_structure("HH", 4) == "HH  "
    assert clean_structure("HHHH", 2) == "HH"
    assert clean_structure("HXE", 3) == "H E"


class _FakeModel:
    def __init__(self, text):
        self.text = text

    def generate(self, protein, config):
        assert config.track == "secondary_structure"
        return types.SimpleNamespace(secondary_structure=self.text)


def test_predict_parses_generated_track(monkeypatch):
    _install_esm_stub(monkeypatch)
    model = _FakeModel("HHHEEGTT")
    assert predict_secondary_structure(model, "ACDEFGHIK", num_steps=4) == "HHHEEGTT "


def test_run_round_trip(monkeypatch):
    _install_esm_stub(monkeypatch)
    form = encode_sequences(["ACDEFGHIK"], "sequence", "position", "protein")
    original = module.load_model
    module.load_model = lambda name, device: _FakeModel("HHHEEGTT")
    try:
        import tempfile

        ctx = Context(tempfile.mkdtemp(), {"params": {}})
        ctx["sequence"] = form
        run(ctx, [{"name": "esm3_secondary_structure", "inputs": ["sequence"], "params": {"output": "ss", "num_steps": 4}}])
    finally:
        module.load_model = original
    result = ctx["ss"]
    assert result.data.shape == (9, 4)
    assert result.info["n_helix"] == 4 and result.info["n_strand"] == 2


def test_errors(monkeypatch):
    form = encode_sequences(["ACDE"], "sequence", "position", "protein")
    ctx = Context("/tmp/operon_esm3_ss_err", {"params": {}})
    ctx["sequence"] = form
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "esm3_secondary_structure", "inputs": ["sequence"], "params": {"output": "ss", "device": "tpu"}}])
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "esm3_secondary_structure", "inputs": ["sequence"], "params": {"output": "ss", "num_steps": 0}}])


@pytest.mark.skipif(
    __import__("importlib").util.find_spec("esm") is None,
    reason="esm package not installed",
)
def test_real_esm3_track():
    import os

    if os.environ.get("OPERON_ESM3_REAL") != "1":
        pytest.skip("set OPERON_ESM3_REAL=1 to run the ESM-3 track")
    model = module.load_model("esm3_sm_open_v1", "cpu")
    text = predict_secondary_structure(model, "MKVLAAGIVGLLLA", num_steps=4)
    assert len(text) == 14
    assert set(text) <= set(" -HBEGITS")
