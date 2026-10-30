"""Hand checks for the 0.50 variance and exact tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.barnard_test import BarnardTestStep
from src.task.step.steps.brown_forsythe import BrownForsytheStep
from src.task.step.steps.levene_test import LeveneTestStep


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


def _grouped():
    values = np.array(
        [1, 2, 3, 4, 100, 2, 4, 6, 8, 20, 10, 20, 30, 40, 50],
        dtype=float,
    )
    groups = ["A"] * 5 + ["B"] * 5 + ["C"] * 5
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(15)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(15)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def _table(table):
    rows, columns = table.shape
    return _form(
        table,
        ["row", "column"],
        {
            "row": {f"r{i}": i for i in range(rows)},
            "column": {f"c{i}": i for i in range(columns)},
        },
    )


def test_levene_matches_descstats():
    expression, meta = _grouped()
    result, out = _run(LeveneTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(3.5958295790964074, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.059760241554658484, rel=1e-6)
    assert out.data[0, 2] == 2
    assert out.data[0, 3] == 12
    assert result["center"] == "mean"


def test_brown_forsythe_matches_descstats():
    expression, meta = _grouped()
    result, out = _run(BrownForsytheStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (1, 6)
    assert out.data[0, 0] == pytest.approx(0.48166623810748233, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(0.6291982673370824, rel=1e-6)
    assert out.data[0, 2] == 2
    assert out.data[0, 3] == 12
    assert result["center"] == "median"


def test_barnard_matches_scipy():
    result, out = _run(BarnardTestStep(), {}, [_table(np.array([[8, 2], [1, 9]], dtype=float))])
    assert out.data.shape == (4,)
    assert out.data[0] == pytest.approx(3.1462660248284626, rel=1e-6)
    assert out.data[1] == pytest.approx(0.0018215179443359397, rel=1e-5)
    assert out.data[2] == pytest.approx(36.0, rel=1e-6)
    assert out.data[3] == 20
    assert result["odds_ratio"] == pytest.approx(36.0)


def test_invalid_inputs():
    with pytest.raises(StepError, match="2x2"):
        _run(BarnardTestStep(), {}, [_table(np.array([[1, 2, 3], [4, 5, 6]], dtype=float))])
    expression, meta = _grouped()
    with pytest.raises(StepError, match="not found"):
        _run(LeveneTestStep(), {"group_label": "missing"}, [expression, meta])
