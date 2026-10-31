"""Hand checks for 0.69 entropy and long-memory operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.approx_entropy import ApproxEntropyStep
from src.task.step.steps.hurst_exponent import HurstExponentStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    form = Form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {"value": 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, values):
    ctx = Ctx(params)
    step.run(ctx, [_form(values)])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _fixture():
    return np.round(np.sin(np.linspace(0, 8 * np.pi, 100)) + 0.1 * np.arange(100) / 100, 1)


def test_approx_entropy_matches_pracma():
    result, out = _run(ApproxEntropyStep(), {"value_label": "value"}, _fixture())
    assert result["approx_entropy"] == pytest.approx(0.19343740801454112, rel=1e-10)
    assert result["embedding_dim"] == 2
    assert result["n"] == 100
    assert out.data.shape == (4, 1)


def test_hurst_matches_pracma_simple_rs():
    result, out = _run(HurstExponentStep(), {"value_label": "value"}, _fixture())
    assert result["hurst"] == pytest.approx(0.54431529367338694, rel=1e-10)
    assert result["n_original"] == 100
    assert result["n_used"] == 100
    assert result["padded"] is False
    assert out.data.shape == (4, 1)


def test_odd_series_pads_like_pracma():
    result, _ = _run(HurstExponentStep(), {"value_label": "value"}, _fixture()[:-1])
    assert result["n_original"] == 99
    assert result["n_used"] == 100
    assert result["padded"] is True


def test_069_rejects_invalid_inputs():
    with pytest.raises(StepError, match="at least 5"):
        _run(ApproxEntropyStep(), {"value_label": "value"}, [1.0, 2.0, 3.0])
    with pytest.raises(StepError, match="radius"):
        _run(ApproxEntropyStep(), {"value_label": "value", "radius": 0}, _fixture())
    with pytest.raises(StepError, match="too short"):
        _run(ApproxEntropyStep(), {"value_label": "value", "embedding_dim": 3}, [1.0, 2.0, 3.0, 4.0, 5.0])
    with pytest.raises(StepError, match="zero variance"):
        _run(HurstExponentStep(), {"value_label": "value"}, np.ones(10))
