"""Hand checks for the 0.28 flow-compensation and causality batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.arch_test import ArchTestStep
from src.task.step.steps.flow_compensate import FlowCompensateStep
from src.task.step.steps.granger_causality import GrangerCausalityStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _series():
    rng = np.random.default_rng(11)
    n = 90
    cause = rng.normal(size=n)
    effect = np.zeros(n)
    for i in range(1, n):
        effect[i] = 0.5 * effect[i - 1] + 0.7 * cause[i - 1] + 0.3 * rng.normal()
    return cause, effect


def test_granger_causality_matches_lmtest():
    cause, effect = _series()
    form = _form(
        np.column_stack([cause, effect]),
        ["sample", "feature"],
        {"sample": _labels([f"t{i}" for i in range(len(cause))]),
         "feature": {"cause": 0, "effect": 1}},
    )
    out, info = _run(
        GrangerCausalityStep(),
        {"cause_label": "cause", "effect_label": "effect", "max_lag": 3},
        [form],
    )
    assert out.data.shape == (3, 4)
    assert np.allclose(
        out.data[:, 0],
        [395.9681448, 211.8084391, 146.0148720],
        atol=1e-4,
    )
    assert np.allclose(out.data[:, 1], info["p"], rtol=1e-6)
    assert np.allclose(out.data[:, 2], [86.0, 83.0, 80.0])
    assert np.allclose(out.data[:, 3], [1.0, 2.0, 3.0])
    assert info["cause"] == "cause"
    assert info["n"] == 90


def test_arch_test_matches_fints():
    rng = np.random.default_rng(5)
    n = 100
    values = rng.normal(size=n) * (1.0 + 0.6 * np.sin(np.arange(n) / 4.0))
    form = _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": _labels([f"t{i}" for i in range(n)]), "feature": {"value": 0}},
    )
    out, info = _run(ArchTestStep(), {"value_label": "value", "lags": 5}, [form])
    assert out.data.shape == (6, 1)
    assert info["lm_statistic"] == pytest.approx(11.4217771216, abs=2e-5)
    assert info["lm_p"] == pytest.approx(0.0436298086, abs=2e-6)
    assert info["lags"] == 5
    assert info["n"] == 100


def test_flow_compensate_matches_flowcore():
    events = _form(
        np.array([[1.0, 0.2, 5.0], [2.0, 0.5, 6.0], [3.0, 0.1, 7.0]]),
        ["event", "channel"],
        {"event": _labels(["e0", "e1", "e2"]),
         "channel": {"A": 0, "B": 1, "C": 2}},
    )
    spillover = _form(
        np.array([[1.0, 0.2], [0.1, 1.0]]),
        ["detector", "fluorochrome"],
        {"detector": _labels(["A", "B"]), "fluorochrome": _labels(["A", "B"])},
    )
    out, info = _run(FlowCompensateStep(), {}, [events, spillover])
    assert out.data.shape == (3, 3)
    assert np.allclose(out.data[0], [1.0, 0.0, 5.0], atol=2e-5)
    assert np.allclose(out.data[1], [1.9897959, 0.1020408, 6.0], atol=2e-5)
    assert np.allclose(out.data[2], [3.0510204, -0.5102041, 7.0], atol=2e-5)
    assert info["channels"] == ["A", "B"]
    assert info["n_events"] == 3
    assert out.labels["channel"]["C"] == 2


def test_new_operators_reject_bad_inputs():
    with pytest.raises(Exception, match="not enough complete observations"):
        form = _form(
            np.zeros((4, 2)),
            ["sample", "feature"],
            {"sample": _labels([f"s{i}" for i in range(4)]),
             "feature": {"cause": 0, "effect": 1}},
        )
        _run(
            GrangerCausalityStep(),
            {"cause_label": "cause", "effect_label": "effect", "max_lag": 3},
            [form],
        )
    with pytest.raises(Exception, match="constant"):
        form = _form(
            np.ones((20, 1)),
            ["sample", "feature"],
            {"sample": _labels([f"s{i}" for i in range(20)]), "feature": {"value": 0}},
        )
        _run(ArchTestStep(), {"value_label": "value", "lags": 3}, [form])
    with pytest.raises(Exception, match="singular"):
        events = _form(
            np.ones((3, 2)),
            ["event", "channel"],
            {"event": _labels(["e0", "e1", "e2"]), "channel": _labels(["A", "B"])},
        )
        spillover = _form(
            np.ones((2, 2)),
            ["detector", "fluorochrome"],
            {"detector": _labels(["A", "B"]), "fluorochrome": _labels(["A", "B"])},
        )
        _run(FlowCompensateStep(), {}, [events, spillover])
