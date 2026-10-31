"""Hand checks for the 0.29 regression diagnostics batch."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.breusch_godfrey import BreuschGodfreyStep
from src.task.step.steps.harvey_collier import HarveyCollierStep
from src.task.step.steps.reset_test import ResetTestStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _form(data):
    form = Form(
        np.asarray(data, dtype=np.float64),
        ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(data.shape[0])]),
         "feature": {"y": 0, "x1": 1, "x2": 2}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _data():
    rng = np.random.default_rng(29)
    n = 50
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    errors = np.zeros(n)
    for i in range(1, n):
        errors[i] = 0.6 * errors[i - 1] + 0.7 * rng.normal()
    y = 1 + 2 * x1 - 1.5 * x2 + 0.4 * x1 * x1 + errors
    return _form(np.column_stack([y, x1, x2]))


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


BASE = {"response_label": "y", "predictors": ["x1", "x2"]}


def test_breusch_godfrey_matches_lmtest():
    out, info = _run(BreuschGodfreyStep(), {**BASE, "lags": 1}, [_data()])
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (7, 1)
    assert info["lm_statistic"] == pytest.approx(2.124298989225432, abs=1e-8)
    assert info["lm_p"] == pytest.approx(0.14497909842931342, abs=1e-9)
    assert info["f_statistic"] == pytest.approx(2.041072014431254, abs=1e-8)
    assert info["f_p"] == pytest.approx(0.1598571996004403, abs=1e-9)
    assert info["df"] == 1
    assert info["n"] == 50


def test_reset_test_matches_lmtest():
    out, info = _run(ResetTestStep(), {**BASE, "power": 2}, [_data()])
    assert out.data.shape == (5, 1)
    assert info["f_statistic"] == pytest.approx(14.00189728854148, abs=1e-7)
    assert info["p"] == pytest.approx(0.0005056801949489, abs=1e-10)
    assert info["df_num"] == 1
    assert info["df_denom"] == 46
    assert info["power"] == 2


def test_harvey_collier_matches_lmtest():
    out, info = _run(HarveyCollierStep(), BASE, [_data()])
    assert out.data.shape == (3, 1)
    assert info["statistic"] == pytest.approx(0.4877593041597246, abs=1e-8)
    assert info["p"] == pytest.approx(0.6280371064766044, abs=1e-9)
    assert info["df"] == 46


def test_diagnostic_parameter_errors():
    step = BreuschGodfreyStep()
    with pytest.raises(StepError, match="lags"):
        _run(step, {**BASE, "lags": 50}, [_data()])
    with pytest.raises(StepError, match="power"):
        _run(ResetTestStep(), {**BASE, "power": 1}, [_data()])
    with pytest.raises(StepError, match="not found"):
        _run(HarveyCollierStep(), {"response_label": "y", "predictors": ["missing"]}, [_data()])
