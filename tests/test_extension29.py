"""Hand checks for 0.36 factorability diagnostics."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.bartlett_sphericity import BartlettSphericityStep
from src.task.step.steps.kmo_test import KmoTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, names):
    data = np.asarray(data, dtype=np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _data():
    return np.asarray(
        [
            [1, 2, 2, 1],
            [2, 3, 3, 2],
            [3, 4, 4, 2],
            [4, 5, 4, 3],
            [5, 6, 5, 4],
            [2, 2, 3, 2],
            [3, 3, 4, 3],
            [4, 4, 5, 4],
            [5, 5, 6, 5],
            [3, 4, 4, 3],
            [2, 3, 2, 2],
            [4, 4, 5, 4],
        ],
        dtype=float,
    )


def test_kmo_matches_psych():
    out, info = _run(
        KmoTestStep(), {}, [_form(_data(), ["v1", "v2", "v3", "v4"])]
    )
    assert out.dims == ["statistic", "value"]
    assert out.data.shape == (5, 1)
    assert info["msa_overall"] == pytest.approx(0.69134199594001244, rel=1e-12)
    assert info["msa"] == pytest.approx(
        {
            "v1": 0.62285347414496506,
            "v2": 0.60687869166303443,
            "v3": 0.82927027254828467,
            "v4": 0.74650102868394264,
        },
        rel=1e-12,
    )
    assert info["n_subjects"] == 12
    assert info["n_variables"] == 4


def test_bartlett_sphericity_matches_psych():
    out, info = _run(
        BartlettSphericityStep(), {}, [_form(_data(), ["v1", "v2", "v3", "v4"])]
    )
    assert out.data.shape == (5, 1)
    assert info["chisq"] == pytest.approx(62.658654013776371, rel=1e-12)
    assert info["df"] == 6
    assert info["p"] == pytest.approx(1.2954623992174981e-11, rel=1e-12)
    assert info["n"] == 12
    assert info["n_variables"] == 4


def test_parameter_errors():
    with pytest.raises(StepError, match="at least two variables"):
        _run(KmoTestStep(), {}, [_form(_data()[:, :1], ["v1"])])
    singular = np.column_stack([_data()[:, 0], _data()[:, 0] * 2.0])
    with pytest.raises(StepError, match="singular"):
        _run(BartlettSphericityStep(), {}, [_form(singular, ["v1", "v2"])])
