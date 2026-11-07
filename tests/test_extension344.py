"""esm3_sasa_prediction: track normalisation and runner contract."""

import types

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps import esm3_sasa_prediction as module
from src.task.step.steps._sequence_common import encode_sequences
from src.task.step.steps.esm3_sasa_prediction import normalise_sasa, predict_sasa


def _install_esm_stub(monkeypatch):
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


def test_normalise_pads_and_truncates():
    assert normalise_sasa([1.0, 2.0], 3).tolist()[0] == 1.0
    assert np.isnan(normalise_sasa([1.0, 2.0], 3)[2])
    assert len(normalise_sasa([1.0, 2.0, 3.0, 4.0], 2)) == 2
    with pytest.raises(StepError, match="empty SASA track"):
        normalise_sasa([], 0)


class _FakeModel:
    def __init__(self, values):
        self.values = values

    def generate(self, protein, config):
        assert config.track == "sasa"
        return types.SimpleNamespace(sasa=self.values)


def test_predict_reads_track(monkeypatch):
    _install_esm_stub(monkeypatch)
    values = predict_sasa(_FakeModel([1.0, 2.0, 3.0]), "ACD", num_steps=4)
    assert values.tolist() == [1.0, 2.0, 3.0]


def test_run_round_trip(monkeypatch):
    _install_esm_stub(monkeypatch)
    form = encode_sequences(["ACDEFGHIK"], "sequence", "position", "protein")
    original = module.load_model
    module.load_model = lambda name, device: _FakeModel([10.0, 30.0, 50.0, 5.0, 5.0, 5.0, 5.0, 5.0, 5.0])
    try:
        import tempfile

        ctx = Context(tempfile.mkdtemp(), {"params": {}})
        ctx["sequence"] = form
        run(ctx, [{"name": "esm3_sasa_prediction", "inputs": ["sequence"], "params": {"output": "sasa", "num_steps": 4}}])
    finally:
        module.load_model = original
    result = ctx["sasa"]
    assert result.data.shape == (9, 2)
    assert result.info["max_sasa"] == 50.0


def test_errors():
    form = encode_sequences(["ACDE"], "sequence", "position", "protein")
    ctx = Context("/tmp/operon_esm3_sasa_err", {"params": {}})
    ctx["sequence"] = form
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "esm3_sasa_prediction", "inputs": ["sequence"], "params": {"output": "sasa", "num_steps": 0}}])


@pytest.mark.skipif(__import__("importlib").util.find_spec("esm") is None, reason="esm package not installed")
def test_real_esm3_sasa():
    import os

    if os.environ.get("OPERON_ESM3_REAL") != "1":
        pytest.skip("set OPERON_ESM3_REAL=1 to run the ESM-3 SASA track")
    model = module.load_model("esm3_sm_open_v1", "cpu")
    values = predict_sasa(model, "MKVLAAGIVGLLLA", num_steps=4)
    assert len(values) == 14
    assert np.isfinite(values).all()
