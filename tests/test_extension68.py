"""Hand checks for 0.75 correspondence analysis and Tobit regression."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.core import Form, StepError
from src.task.step.steps.correspondence_analysis import CorrespondenceAnalysisStep
from src.task.step.steps.tobit import TobitStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _table(values, row_dim="row", column_dim="column"):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=[row_dim, column_dim],
        labels={
            row_dim: {f"r{i}": i for i in range(values.shape[0])},
            column_dim: {f"c{j}": j for j in range(values.shape[1])},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _tobit_fixture():
    rng = np.random.default_rng(20261103)
    n = 60
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1.2 + 0.9 * x1 - 0.6 * x2 + rng.normal(scale=1.1, size=n)
    frame = pd.DataFrame({"y": np.maximum(y, 0.0), "x1": x1, "x2": x2})
    form = Form(
        data=frame.to_numpy(dtype=float),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(n)},
            "feature": {"y": 0, "x1": 1, "x2": 2},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def test_correspondence_analysis_matches_ca():
    table = [[10, 20, 30], [20, 40, 20], [30, 10, 10], [15, 25, 35]]
    export, out = _run(
        CorrespondenceAnalysisStep(), {"output": "ca"}, [_table(table)]
    )
    assert out.dims == ["point", "component"]
    assert out.data.shape == (7, 2)
    expected = np.asarray(
        [
            [-0.28692357472544877, 0.15209520681266003],
            [-0.02419146280797372, -0.30324681824601774],
            [0.69426278711411527, 0.11470430316855122],
            [-0.20749877130054584, 0.12531757189992332],
            [0.54837926674161341, 0.051841944555907647],
            [-0.14923957022464157, -0.25328668239160979],
            [-0.28369142983452672, 0.21235883142641962],
        ]
    )
    np.testing.assert_allclose(out.data, expected, rtol=1e-12, atol=1e-14)
    assert export["singular_values"] == pytest.approx(
        [0.34920690627954476, 0.19981461817371882], rel=1e-12
    )
    assert export["total_inertia"] == pytest.approx(0.16187134502923978, rel=1e-12)
    assert export["chi_square"] == pytest.approx(42.89590643274854, rel=1e-12)
    assert export["df"] == 6
    expected_std_rows = np.asarray(
        [
            [-0.82164347143742522, 0.76118158022066484],
            [-0.069275442074470686, -1.5176408063516904],
            [1.988112991552202, 0.57405361137705813],
            [-0.59420007900542593, 0.62716918834723212],
        ]
    )
    expected_std_cols = np.asarray(
        [
            [1.5703563041866893, 0.25945020954791342],
            [-0.4273671784290925, -1.2676083697309992],
            [-0.81238779856039844, 1.0627792569300154],
        ]
    )
    np.testing.assert_allclose(
        export["standard_row_coordinates"], expected_std_rows, rtol=1e-12, atol=1e-14
    )
    np.testing.assert_allclose(
        export["standard_column_coordinates"], expected_std_cols, rtol=1e-12, atol=1e-14
    )
    assert out.info["n_rows"] == 4
    assert out.info["n_columns"] == 3


def test_correspondence_analysis_components_and_contributions():
    table = [[10, 20, 30], [20, 40, 20], [30, 10, 10], [15, 25, 35]]
    export, out = _run(
        CorrespondenceAnalysisStep(),
        {"n_components": 1, "output": "ca"},
        [_table(table)],
    )
    assert out.data.shape == (7, 1)
    assert export["cumulative"][-1] == pytest.approx(0.7533, abs=1e-4)
    row_contribution = np.asarray(export["row_contribution"])
    column_contribution = np.asarray(export["column_contribution"])
    assert row_contribution.sum() == pytest.approx(1.0, abs=1e-12)
    assert column_contribution.sum() == pytest.approx(1.0, abs=1e-12)
    assert np.all(np.asarray(export["row_cos2"]) >= 0)
    assert np.all(np.asarray(export["row_cos2"]) <= 1 + 1e-12)
    assert np.all(np.asarray(export["column_cos2"]) >= 0)
    assert np.all(np.asarray(export["column_cos2"]) <= 1 + 1e-12)


def test_tobit_matches_censreg():
    export, out = _run(
        TobitStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "fit"},
        [_tobit_fixture()],
    )
    assert out.dims == ["term", "statistic"]
    assert out.data.shape == (3, 6)
    expected_coef = [1.10646400866156114, 0.91970907755316011, -0.60664699838834946]
    expected_se = [0.11553127141226120, 0.11778270999030564, 0.12791704775948415]
    assert out.data[:, 0] == pytest.approx(expected_coef, abs=2e-6)
    assert out.data[:, 1] == pytest.approx(expected_se, abs=2e-6)
    assert out.data[:, 4] == pytest.approx(
        [0.8800269, 0.6888592, -0.8573598], abs=1e-5
    )
    assert out.data[:, 5] == pytest.approx(
        [1.3329011, 1.1505589, -0.3559342], abs=1e-5
    )
    assert export["terms"] == ["Intercept", "x1", "x2"]
    assert export["sigma"] == pytest.approx(0.8373168628959122, abs=1e-7)
    assert export["loglik"] == pytest.approx(-67.50745588161293, abs=1e-8)
    assert export["n"] == 60
    assert export["n_censored"] == 11


def test_075_rejects_invalid_inputs():
    with pytest.raises(StepError, match="nonnegative"):
        _run(CorrespondenceAnalysisStep(), {}, [_table([[1, -1], [2, 3]])])
    with pytest.raises(StepError, match="positive margin"):
        _run(CorrespondenceAnalysisStep(), {}, [_table([[1, 0], [2, 0]])])
    with pytest.raises(StepError, match="at least two rows"):
        _run(CorrespondenceAnalysisStep(), {}, [_table([[1], [2]])])
    with pytest.raises(StepError, match="empty"):
        _run(CorrespondenceAnalysisStep(), {}, [_table([[0, 0], [0, 0]])])

    form = _tobit_fixture()
    form.data[:, 0] = 0.0
    with pytest.raises(StepError, match="all observations are censored"):
        _run(
            TobitStep(),
            {"response_label": "y", "predictors": ["x1", "x2"]},
            [form],
        )
    small = _tobit_fixture()
    small.data = small.data[:3].copy()
    small.labels["sample"] = {f"s{i}": i for i in range(3)}
    with pytest.raises(StepError, match="fewer than four"):
        _run(
            TobitStep(),
            {"response_label": "y", "predictors": ["x1", "x2"]},
            [small],
        )
