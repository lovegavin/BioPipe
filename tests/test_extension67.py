"""Hand checks for 0.74 CUSUM and EWMA control charts."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cusum_chart import CusumChartStep
from src.task.step.steps.ewma_chart import EwmaChartStep


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


def _series():
    return np.asarray([10, 12, 11, 13, 12, 14, 13, 15, 14, 16, 15, 17], dtype=float)


def test_cusum_chart_matches_qcc():
    result, out = _run(CusumChartStep(), {"value_label": "y", "output": "out"}, [_form(_series())])
    assert out.dims == ["sample", "statistic"]
    assert out.data.shape == (12, 6)
    expected_pos = [
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.5948235294117645,
        0.4597647058823527,
        1.7844705882352936,
        2.379294117647058,
        4.4338823529411755,
    ]
    expected_neg = [
        -2.0545882352941174,
        -2.649411764705882,
        -3.974117647058823,
        -3.8390588235294114,
        -4.4338823529411755,
        -3.568941176470587,
        -3.4338823529411755,
        -1.839058823529411,
        -0.9741176470588229,
        0.0,
        0.0,
        0.0,
    ]
    assert out.data[:, 0] == pytest.approx(expected_pos, abs=1e-6)
    assert out.data[:, 1] == pytest.approx(expected_neg, abs=1e-6)
    assert out.data[:, 2] == pytest.approx(np.full(12, 13.5), abs=1e-6)
    assert out.data[:, 3] == pytest.approx(np.full(12, 1.3700838168923277), abs=1e-6)
    assert out.data[:, 4] == pytest.approx(np.full(12, 5.0), abs=1e-9)
    assert not out.data[:, 5].any()
    assert result["center"] == pytest.approx(13.5, abs=1e-9)
    assert result["std_dev"] == pytest.approx(1.3700838168923277, abs=1e-9)
    assert result["out_of_control_count"] == 0


def test_ewma_chart_matches_qcc():
    result, out = _run(EwmaChartStep(), {"value_label": "y", "output": "out"}, [_form(_series())])
    assert out.data.shape == (12, 6)
    expected_ewma = [
        12.8,
        12.64,
        12.312,
        12.4496,
        12.35968,
        12.687744,
        12.7501952,
        13.20015616,
        13.360124928,
        13.8880999424,
        14.11047995392,
        14.688383963136,
    ]
    expected_lcl = [
        12.677949709864604,
        12.447261972569068,
        12.323117938650114,
        12.250120179072775,
        12.205560197522196,
        12.177829701988241,
        12.160383402030202,
        12.149336029048069,
        12.142312884547628,
        12.137837075189045,
        12.134980259080994,
        12.133155030336363,
    ]
    expected_ucl = [
        14.322050290135396,
        14.552738027430932,
        14.676882061349886,
        14.749879820927225,
        14.794439802477804,
        14.822170298011759,
        14.839616597969798,
        14.850663970951931,
        14.857687115452372,
        14.862162924810955,
        14.865019740919006,
        14.866844969663637,
    ]
    assert out.data[:, 0] == pytest.approx(expected_ewma, abs=1e-6)
    assert out.data[:, 1] == pytest.approx(np.full(12, 13.5), abs=1e-6)
    assert out.data[:, 2] == pytest.approx(expected_lcl, abs=1e-6)
    assert out.data[:, 3] == pytest.approx(expected_ucl, abs=1e-6)
    assert out.data[:, 4] == pytest.approx(np.full(12, 1.3700838168923277), abs=1e-6)
    assert out.data[:, 5].tolist() == [0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    assert result["lambda"] == pytest.approx(0.2, abs=1e-12)
    assert result["out_of_control_count"] == 1


def test_control_chart_parameters_change_sensitivity():
    _, strict = _run(
        EwmaChartStep(),
        {"value_label": "y", "lambda": 0.2, "nsigmas": 2.0, "output": "out"},
        [_form(_series())],
    )
    _, default = _run(
        EwmaChartStep(),
        {"value_label": "y", "output": "out"},
        [_form(_series())],
    )
    strict_width = (strict.data[:, 3] - strict.data[:, 2]).mean()
    default_width = (default.data[:, 3] - default.data[:, 2]).mean()
    assert strict_width < default_width
    assert strict.data.shape == default.data.shape == (12, 6)


def test_074_rejects_invalid_inputs():
    with pytest.raises(StepError, match="non-zero variation"):
        _run(CusumChartStep(), {"value_label": "y"}, [_form(np.ones(20))])
    with pytest.raises(StepError, match="at least 3"):
        _run(EwmaChartStep(), {"value_label": "y"}, [_form([1.0, 2.0])])
    with pytest.raises(StepError, match="lambda"):
        _run(EwmaChartStep(), {"value_label": "y", "lambda": 0.0}, [_form(_series())])
    with pytest.raises(StepError, match="decision_interval"):
        _run(CusumChartStep(), {"value_label": "y", "decision_interval": 0.0}, [_form(_series())])
    with pytest.raises(StepError, match="not found"):
        _run(CusumChartStep(), {"value_label": "missing"}, [_form(_series())])
