"""Hand and deterministic checks for the 0.77 power operators."""
from __future__ import annotations

import pytest

from src.core import StepError
from src.task.step.steps.power_anova import PowerAnovaStep
from src.task.step.steps.power_prop_test import PowerPropTestStep
from src.task.step.steps.power_t_test import PowerTTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_power_t_test_matches_statsmodels_and_r():
    result, out = _run(PowerTTestStep(), {"effect_size": 0.5, "nobs1": 64})
    assert out.data.shape == (6, 1)
    assert result["power"] == pytest.approx(0.8014595579222542, abs=1e-12)
    assert result["effect_size"] == pytest.approx(0.5, abs=1e-12)
    assert result["nobs1"] == 64
    assert result["nobs2"] == 64
    assert result["df"] == 126
    assert out.data[0, 0] == pytest.approx(result["power"], abs=1e-12)

    paired, _ = _run(
        PowerTTestStep(),
        {"test": "paired", "effect_size": 0.5, "nobs1": 64},
    )
    assert paired["power"] == pytest.approx(0.9760555768876558, abs=1e-12)
    assert paired["df"] == 63

    one_sample, _ = _run(
        PowerTTestStep(),
        {"test": "one-sample", "effect_size": 0.5, "nobs1": 64},
    )
    assert one_sample["power"] == pytest.approx(paired["power"], abs=1e-12)

    greater, _ = _run(
        PowerTTestStep(),
        {"effect_size": 0.5, "nobs1": 64, "alternative": "greater"},
    )
    assert greater["power"] > result["power"]


def test_power_prop_test_matches_statsmodels_and_r():
    result, out = _run(
        PowerPropTestStep(),
        {"p1": 0.6, "p2": 0.4, "nobs1": 100, "nobs2": 100},
    )
    assert out.data.shape == (7, 1)
    assert result["effect_size"] == pytest.approx(0.40271584158066154, abs=1e-15)
    assert result["power"] == pytest.approx(0.8126408236244113, abs=1e-12)
    assert result["nobs1"] == 100
    assert result["nobs2"] == 100


def test_power_anova_matches_statsmodels_and_r():
    result, out = _run(
        PowerAnovaStep(),
        {"effect_size": 0.25, "n_per_group": 40, "k_groups": 4},
    )
    assert out.data.shape == (8, 1)
    assert result["power"] == pytest.approx(0.7494045377009664, abs=1e-10)
    assert result["n_per_group"] == 40
    assert result["n_total"] == 160
    assert result["df1"] == 3
    assert result["df2"] == 156


def test_power_operators_reject_invalid_inputs():
    with pytest.raises(StepError, match="greater than"):
        _run(PowerTTestStep(), {"effect_size": 0.0, "nobs1": 60})
    with pytest.raises(StepError, match="test must be"):
        _run(PowerTTestStep(), {"effect_size": 0.5, "nobs1": 60, "test": "nope"})
    with pytest.raises(StepError, match="in \\[0, 1\\]"):
        _run(PowerPropTestStep(), {"p1": 1.2, "p2": 0.4, "nobs1": 50, "nobs2": 50})
    with pytest.raises(StepError, match="must differ"):
        _run(PowerPropTestStep(), {"p1": 0.5, "p2": 0.5, "nobs1": 50, "nobs2": 50})
    with pytest.raises(StepError, match="at least 2"):
        _run(PowerAnovaStep(), {"effect_size": 0.25, "n_per_group": 40, "k_groups": 1})
    with pytest.raises(StepError, match="less than 1.0"):
        _run(PowerAnovaStep(), {"effect_size": 0.25, "n_per_group": 40, "k_groups": 4, "alpha": 1.0})
