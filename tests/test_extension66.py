"""Hand and deterministic checks for 0.73 unit-root and ARCH tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.arch_lm import ArchLmStep
from src.task.step.steps.dfgls import DfglsStep
from src.task.step.steps.phillips_perron import PhillipsPerronStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {"y": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _pp_values():
    rng = np.random.default_rng(20261102)
    return np.cumsum(rng.normal(size=120))


def test_phillips_perron_matches_arch_and_r():
    y = _pp_values()
    result, out = _run(PhillipsPerronStep(), {"value_label": "y", "lags": 2}, [_form(y)])
    assert out.data.shape == (8, 1)
    assert result["statistic"] == pytest.approx(-1.9273077985416451, abs=1e-12)
    assert result["p"] == pytest.approx(0.31932569624470114, rel=1e-12)
    assert result["lags"] == 2
    assert result["nobs"] == 119
    assert out.data[0, 0] == pytest.approx(result["statistic"], abs=1e-12)
    assert out.data[5, 0] == pytest.approx(result["critical"]["1%"], abs=1e-12)


def test_dfgls_matches_arch_and_r():
    y = _pp_values()
    result, out = _run(DfglsStep(), {"value_label": "y", "lags": 2}, [_form(y)])
    assert out.data.shape == (9, 1)
    assert result["statistic"] == pytest.approx(-1.74135623062118, abs=1e-12)
    assert result["p"] == pytest.approx(0.08039437046328551, abs=1e-12)
    assert result["lags"] == 2
    assert result["nobs"] == 117
    assert out.data[0, 0] == pytest.approx(result["statistic"], abs=1e-12)


def test_arch_lm_matches_statsmodels():
    rng = np.random.default_rng(20261102)
    e = rng.standard_t(5, size=200)
    result, out = _run(ArchLmStep(), {"value_label": "y", "lags": 5}, [_form(e)])
    assert out.data.shape == (7, 1)
    assert result["statistic"] == pytest.approx(4.186145832492666, abs=1e-12)
    assert result["p"] == pytest.approx(0.5229387617060965, rel=1e-12)
    assert result["f_statistic"] == pytest.approx(0.829270564019495, abs=1e-12)
    assert result["f_p"] == pytest.approx(0.5303006600082081, rel=1e-12)
    assert result["df"] == 5


def test_073_rejects_invalid_inputs():
    with pytest.raises(StepError, match="positive variance"):
        _run(PhillipsPerronStep(), {"value_label": "y"}, [_form(np.ones(20))])
    with pytest.raises(StepError, match="at least 10"):
        _run(DfglsStep(), {"value_label": "y"}, [_form(np.arange(9.0))])
    with pytest.raises(StepError, match="less than n - 1"):
        _run(ArchLmStep(), {"value_label": "y", "lags": 9}, [_form(np.arange(10.0))])
