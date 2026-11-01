"""Tests for the 1.12.0 normality and trend operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cox_stuart import CoxStuartStep
from src.task.step.steps.lilliefors_test import LillieforsTestStep
from src.task.step.steps.pearson_test import PearsonTestStep
from src.task.step.steps.rank_test import RankTestStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    samples = [f"s{index}" for index in range(data.shape[0])]
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {name: index for index, name in enumerate(samples)},
                "feature": {"value": 0}},
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _run(step, values, **params):
    settings = {"value_label": "value", "output": "out"}
    settings.update(params)
    ctx = Ctx(settings)
    step.run(ctx, (_form(values),))
    return ctx["out"], step.export(ctx)


def _row(result, names):
    values = result.data[0]
    return {name: float(values[index]) for index, name in enumerate(names)}


LILLIE_X = [0.13, 0.25, 0.31, 0.44, 0.52, 0.61, 0.72, 0.81, 0.92, 1.05]
RANK_X = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3]
PEARSON_X = [-1.2, -0.5, -0.3, -0.1, 0.0, 0.2, 0.4, 0.6, 0.9, 1.1,
             1.4, 1.7, 2.0, 2.4, 2.9, 3.3, 3.9, 4.6, 5.5, 7.0]


def test_lilliefors_matches_nortest():
    result, exported = _run(LillieforsTestStep(), LILLIE_X)
    assert list(result.dims) == ["test", "value"]
    values = _row(result, ["statistic", "p_value", "n"])
    assert values["statistic"] == pytest.approx(0.11130902375462534, rel=1e-5)
    assert values["p_value"] == pytest.approx(0.97780253575171683, rel=1e-5)
    assert values["n"] == 10
    assert exported["statistic"] == pytest.approx(values["statistic"], rel=1e-6)


def test_lilliefors_rejects_small_and_constant_samples():
    with pytest.raises(StepError, match="at least five"):
        _run(LillieforsTestStep(), [1.0, 2.0, 3.0, 4.0])
    with pytest.raises(StepError, match="constant"):
        _run(LillieforsTestStep(), [2.0] * 6)


def test_cox_stuart_matches_randtests():
    result, exported = _run(CoxStuartStep(), [1, 5, 2, 8, 3, 9, 4, 10, 6, 11, 7, 12])
    values = _row(result, ["pairs_increasing", "n_pairs", "p_value"])
    assert values["pairs_increasing"] == 6
    assert values["n_pairs"] == 6
    assert values["p_value"] == pytest.approx(0.03125, abs=1e-6)
    assert exported["p_value"] == pytest.approx(0.03125, abs=1e-9)


def test_cox_stuart_short_series_and_ties():
    result, _ = _run(CoxStuartStep(), [2, 1, 4, 3, 6, 5, 8, 7])
    values = _row(result, ["pairs_increasing", "n_pairs", "p_value"])
    assert values["pairs_increasing"] == 4
    assert values["n_pairs"] == 4
    assert values["p_value"] == pytest.approx(0.125, abs=1e-6)
    result, _ = _run(CoxStuartStep(), [5, 5, 5, 5, 5, 5])
    values = _row(result, ["pairs_increasing", "n_pairs", "p_value"])
    assert values["n_pairs"] == 0
    assert values["p_value"] == pytest.approx(1.0, abs=1e-6)


def test_rank_test_matches_randtests():
    result, exported = _run(RankTestStep(), RANK_X)
    values = _row(result, ["statistic", "P", "expected", "variance", "p_value", "n"])
    assert values["statistic"] == pytest.approx(1.7108556417848431, rel=1e-5)
    assert values["P"] == 79
    assert values["expected"] == 60
    assert values["variance"] == pytest.approx(123.33333333333333, rel=1e-6)
    assert values["p_value"] == pytest.approx(0.08710776496743855, rel=1e-5)
    assert values["n"] == 16
    assert exported["P"] == 79


def test_rank_test_monotone_series():
    result, _ = _run(RankTestStep(), list(range(10)))
    assert result.data[0, 1] == 45
    assert result.data[0, 0] > 4.0
    assert result.data[0, 4] < 1e-4


def test_pearson_test_matches_nortest():
    result, exported = _run(PearsonTestStep(), PEARSON_X)
    values = _row(result, ["statistic", "df", "p_value", "n_classes", "n"])
    assert values["statistic"] == pytest.approx(5.2000000000000011, rel=1e-6)
    assert values["df"] == 4
    assert values["p_value"] == pytest.approx(0.2673848815716019, rel=1e-6)
    assert values["n_classes"] == 7
    assert values["n"] == 20
    assert exported["df"] == 4


def test_pearson_test_explicit_classes_without_adjustment():
    result, _ = _run(PearsonTestStep(), PEARSON_X, n_classes=4, adjust=False)
    assert result.data[0, 3] == 4
    assert result.data[0, 4] == 20
    assert result.info["adjust"] is False


def test_pearson_test_rejects_tiny_samples():
    with pytest.raises(StepError, match="at least five"):
        _run(PearsonTestStep(), [1.0, 2.0, 3.0])
