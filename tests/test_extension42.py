"""Hand checks for the 0.49 block-rank and trend tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.cuzick_test import CuzickTestStep
from src.task.step.steps.durbin_test import DurbinTestStep
from src.task.step.steps.skillings_mack import SkillingsMackTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _durbin():
    matrix = np.array(
        [
            [1, 2, 3, np.nan],
            [4, 5, np.nan, 6],
            [7, np.nan, 8, 9],
            [np.nan, 10, 11, 12],
        ],
        dtype=float,
    )
    return _form(
        matrix,
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(4)},
            "treatment": {f"T{i}": i for i in range(4)},
        },
    )


def _skillings():
    matrix = np.array(
        [
            [1, 2, 3, np.nan],
            [2, 3, np.nan, 4],
            [3, np.nan, 4, 5],
            [np.nan, 4, 5, 6],
            [5, 6, np.nan, 7],
        ],
        dtype=float,
    )
    return _form(
        matrix,
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(5)},
            "treatment": {f"T{i}": i for i in range(4)},
        },
    )


def _grouped():
    values = np.array([1, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13], dtype=float)
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(18)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(18)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def test_durbin_matches_pmcmrplus():
    result, out = _run(DurbinTestStep(), {}, [_durbin()])
    assert out.data.shape == (7, 1)
    assert result["statistic"] == pytest.approx(7.5, rel=1e-6)
    assert result["df"] == 3
    assert result["p"] == pytest.approx(0.057558451972636406, rel=1e-6)
    assert result["n_blocks"] == 4
    assert result["n_treatments"] == 4
    assert result["n_per_block"] == 3
    assert result["n_replicates"] == 3


def test_skillings_mack_matches_pmcmrplus():
    result, out = _run(SkillingsMackTestStep(), {}, [_skillings()])
    assert out.data.shape == (6, 1)
    assert result["statistic"] == pytest.approx(9.4090909090909083, rel=1e-6)
    assert result["df"] == 3
    assert result["p"] == pytest.approx(0.02431840851015896, rel=1e-6)
    assert result["n_blocks"] == 5
    assert result["n_treatments"] == 4
    assert result["n_observations"] == 15


def test_cuzick_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(CuzickTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (1, 5)
    assert result["n_groups"] == 3
    assert result["scores"] == [1.0, 2.0, 3.0]
    assert out.data[0, 0] == pytest.approx(3.5418343613549821, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.00039735490558644653, rel=1e-6)
    assert out.data[0, 2] == pytest.approx(407.5, rel=1e-6)


def test_049_rejects_invalid_inputs():
    complete = _durbin()
    complete.data[np.isnan(complete.data)] = 0.0
    with pytest.raises(StepError, match="incomplete"):
        _run(DurbinTestStep(), {}, [complete])

    unbalanced = _durbin()
    unbalanced.data[1, 0] = np.nan
    with pytest.raises(StepError, match="balanced"):
        _run(DurbinTestStep(), {}, [unbalanced])

    missing_block = _skillings()
    missing_block.data[0, :] = np.nan
    with pytest.raises(StepError, match="at least two"):
        _run(SkillingsMackTestStep(), {}, [missing_block])

    expression, meta = _grouped()
    with pytest.raises(StepError, match="not found"):
        _run(CuzickTestStep(), {"group_label": "absent"}, [expression, meta])
