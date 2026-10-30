"""Hand tests for 0.26 flow-cytometry operators."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core import StepError
from src.reader.readers.fcs_reader import FcsReader
from src.task.step.steps.flow_gate import FlowGateStep
from src.task.step.steps.flow_transform import FlowTransformStep


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form():
    return FcsReader().read(
        FIXTURES / "fcs_example.fcs",
        ["event", "channel"],
        {"event": "auto", "channel": "builtin"},
    )


def test_flow_transform_matches_flowcore():
    ctx = Ctx({"channels": ["FSC-H", "FL1-H"], "a": 0.0, "b": 1.0, "c": 5.0})
    step = FlowTransformStep()
    step.run(ctx, [_form()])
    out = ctx["flow_transform"]
    out.validate()
    row = out.data[0]
    assert row[0] == pytest.approx(11.63857, abs=1e-4)
    assert row[2] == pytest.approx(12.11964, abs=1e-4)
    assert row[1] == pytest.approx(77.0)
    assert out.info["representation"] == "flow_arcsinh"


def test_flow_transform_default_formula():
    ctx = Ctx({"channels": ["FSC-H"]})
    step = FlowTransformStep()
    step.run(ctx, [_form()])
    assert ctx["flow_transform"].data[0, 0] == pytest.approx(float(np.arcsinh(1.0 + 382.0)), abs=1e-6)


def test_flow_gate_matches_flowcore():
    ctx = Ctx({
        "x_channel": "FSC-H",
        "y_channel": "SSC-H",
        "x_min": 100.0,
        "x_max": 500.0,
        "y_min": 50.0,
        "y_max": 400.0,
    })
    step = FlowGateStep()
    step.run(ctx, [_form()])
    out = step.export(ctx)
    assert out["n_inside"] == 6959
    assert out["proportion"] == pytest.approx(0.6959, abs=1e-12)
    assert out["n_total"] == 10000


def test_flow_gate_rejects_bad_channel():
    ctx = Ctx({
        "x_channel": "missing",
        "y_channel": "SSC-H",
        "x_min": 0.0,
        "x_max": 1.0,
        "y_min": 0.0,
        "y_max": 1.0,
    })
    with pytest.raises(StepError, match="channel"):
        FlowGateStep().run(ctx, [_form()])
