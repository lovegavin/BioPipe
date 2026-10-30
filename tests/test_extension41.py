"""Hand checks for the 0.48 post-hoc and block tests."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.conover_test import ConoverTestStep
from src.task.step.steps.games_howell import GamesHowellStep
from src.task.step.steps.quade_test import QuadeTestStep


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


def _quade():
    matrix = np.array(
        [
            [1, 2, 3],
            [2, 4, 6],
            [3, 6, 9],
            [4, 8, 12],
            [5, 10, 15],
        ],
        dtype=float,
    )
    return _form(
        matrix,
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(5)},
            "treatment": {"T1": 0, "T2": 1, "T3": 2},
        },
    )


def test_conover_matches_descstats():
    expression, meta = _grouped()
    result, out = _run(ConoverTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (3, 7)
    assert np.allclose(out.data[:, 0], [-4.8333333333333339, -10.9166666666666661, -6.0833333333333321], rtol=1e-6, atol=1e-7)
    assert np.allclose(
        out.data[:, 2],
        [0.010462063490453718, 2.5080247917311833e-05, 0.0044497715042364737],
        rtol=1e-6,
        atol=1e-8,
    )
    assert result["n_groups"] == 3
    assert result["n_comparisons"] == 3
    assert result["adjustment"] == "holm"


def test_games_howell_matches_pmcmrplus():
    expression, meta = _grouped()
    result, out = _run(GamesHowellStep(), {"group_label": "group"}, [expression, meta])
    assert out.data.shape == (3, 8)
    assert np.allclose(out.data[:, 0], [-3.0, -7.0, -4.0], rtol=1e-6, atol=1e-7)
    assert np.allclose(out.data[:, 1], [3.9279220242478630, 9.1651513899116797, 5.2372293656638176], rtol=1e-6, atol=1e-7)
    assert np.allclose(
        out.data[:, 3],
        [0.047125923759940624, 0.00018923503262868735, 0.010381720683943052],
        rtol=1e-6,
        atol=1e-8,
    )
    assert result["n_comparisons"] == 3


def test_quade_matches_stats():
    result, out = _run(QuadeTestStep(), {}, [_quade()])
    assert out.data.shape == (6, 1)
    assert result["F"] == pytest.approx(18.0, rel=1e-6)
    assert result["df1"] == 2
    assert result["df2"] == 8
    assert result["p"] == pytest.approx(0.0010928215285841132, rel=1e-8)


def test_048_rejects_invalid_inputs():
    expression, meta = _grouped()
    with pytest.raises(StepError, match="group"):
        _run(ConoverTestStep(), {"group_label": "missing"}, [expression, meta])
    bad = _quade()
    bad.data[1, 1] = np.nan
    with pytest.raises(StepError, match="missing"):
        _run(QuadeTestStep(), {}, [bad])
