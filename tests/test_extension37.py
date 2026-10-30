"""Hand checks for the 0.44 trend/outlier/normality tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.anderson_darling import AndersonDarlingStep
from src.task.step.steps.cox_stuart_test import CoxStuartTestStep
from src.task.step.steps.grubbs_test import GrubbsTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"x": 0},
        },
    )


def _trend_series():
    return [1, 2, 4, 3, 5, 7, 6, 8, 9, 11, 10, 12, 14, 13, 15, 17, 16, 18, 19, 21]


def test_cox_stuart_matches_randtests():
    result, out = _run(CoxStuartTestStep(), {"value_label": "x"}, [_series(_trend_series())])
    assert result["t"] == 10
    assert result["n"] == 10
    assert result["n_pairs"] == 10
    assert result["ties"] == 0
    assert result["p"] == pytest.approx(0.001953125, rel=1e-12)
    assert out.data.shape == (5, 1)


def test_cox_stuart_drops_middle_and_ties():
    values = [1, 2, 3, 4, 1, 5, 6]
    result, _ = _run(CoxStuartTestStep(), {"value_label": "x"}, [_series(values)])
    assert result["n_pairs"] == 3
    assert result["ties"] == 1
    assert result["t"] == 2
    assert result["p"] == pytest.approx(0.5, rel=1e-12)


def test_grubbs_matches_outliers_package():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 25]
    result, out = _run(GrubbsTestStep(), {"value_label": "x"}, [_series(values)])
    assert result["G"] == pytest.approx(2.709117334893635, rel=1e-12)
    assert result["U"] == pytest.approx(0.19267515923566875, rel=1e-12)
    assert result["p"] == pytest.approx(0.00093820829159652064, rel=1e-9)
    assert result["outlier"] == 25
    assert result["direction"] == "high"
    assert out.data.shape == (5, 1)


def test_anderson_darling_matches_nortest():
    result, out = _run(AndersonDarlingStep(), {"value_label": "x"}, [_series(_trend_series())])
    assert result["A"] == pytest.approx(0.18980837048798804, rel=1e-12)
    assert result["p"] == pytest.approx(0.88712429103709245, rel=1e-12)
    assert result["n"] == 20
    assert out.data.shape == (4, 1)


def test_044_rejects_invalid_inputs():
    with pytest.raises(StepError, match="at least two"):
        _run(CoxStuartTestStep(), {"value_label": "x"}, [_series([1.0])])
    with pytest.raises(StepError, match="zero variance"):
        _run(GrubbsTestStep(), {"value_label": "x"}, [_series([2.0, 2.0, 2.0])])
    with pytest.raises(StepError, match="at least 8"):
        _run(AndersonDarlingStep(), {"value_label": "x"}, [_series(range(7))])
