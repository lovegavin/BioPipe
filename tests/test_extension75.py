"""Hand checks for 0.82 PCoA and CCA."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.cca import CcaStep
from src.task.step.steps.pcoa import PcoaStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _distance_form(values):
    values = np.asarray(values, dtype=float)
    n = values.shape[0]
    form = Form(
        data=values,
        dims=["sample", "sample_b"],
        labels={
            "sample": {f"s{i}": i for i in range(n)},
            "sample_b": {f"s{i}": i for i in range(n)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _table_form(values, names, dim="feature"):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", dim],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            dim: {name: index for index, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


DISTANCE = np.array(
    [
        [0, 1, 1, 2, 1, 2, 2],
        [1, 0, 2, 1, 2, 1, 3],
        [1, 2, 0, 1, 3, 1, 1],
        [2, 1, 1, 0, 1, 3, 1],
        [1, 2, 3, 1, 0, 2, 2],
        [2, 1, 1, 3, 2, 0, 2],
        [2, 3, 1, 1, 2, 2, 0],
    ],
    dtype=float,
)

PCoA_POINTS = np.array(
    [
        [0.4146201, 0.1704613, 0.007598439],
        [1.2342321, 0.2045695, -0.774967445],
        [-0.5241788, -1.1907602, -0.550612847],
        [-0.8268280, 0.8465124, -0.809682190],
        [0.2173079, 1.3590108, 0.834681538],
        [0.9061619, -1.0818894, 0.709611524],
        [-1.4213152, -0.3079044, 0.583370981],
    ]
)

Y = np.array(
    [
        [10, 20, 30],
        [20, 40, 20],
        [30, 10, 10],
        [15, 25, 35],
        [25, 15, 20],
        [5, 30, 25],
        [20, 20, 40],
        [30, 20, 10],
    ],
    dtype=float,
)
X = np.column_stack(
    [
        [-1, -0.5, 0, 0.5, 1, -1, 0, 1],
        [0, 1, 0, 1, 0, 1, 1, 0],
    ]
)


def test_pcoa_matches_cmdscale():
    export, form = _run(
        PcoaStep(),
        {"n_components": 4, "output": "pcoa"},
        [_distance_form(DISTANCE)],
    )
    assert form.data.shape == (7, 4)
    assert list(form.labels["component"]) == ["PC1", "PC2", "PC3", "PC4"]
    np.testing.assert_allclose(
        export["eigenvalues"],
        [5.542135906022611, 5.317599140996917, 3.0999555198047037, 1.348490145693564],
        rtol=0,
        atol=1e-10,
    )
    np.testing.assert_allclose(
        np.abs(np.asarray(export["coordinates"])[:, :3]),
        np.abs(PCoA_POINTS),
        rtol=0,
        atol=2e-6,
    )
    assert export["n_positive"] == 4
    assert export["n_negative"] == 2


def test_pcoa_rejects_bad_distance():
    bad = DISTANCE.copy()
    bad[0, 0] = 0.5
    with pytest.raises(StepError, match="diagonal must be zero"):
        _run(PcoaStep(), {"output": "p"}, [_distance_form(bad)])
    bad = DISTANCE.copy()
    bad[0, 1] = bad[1, 0] = -1.0
    with pytest.raises(StepError, match="nonnegative"):
        _run(PcoaStep(), {"output": "p"}, [_distance_form(bad)])


def test_cca_matches_vegan():
    export, form = _run(
        CcaStep(),
        {"n_components": 2, "output": "cca"},
        [_table_form(Y, ["sp1", "sp2", "sp3"]), _table_form(X, ["x1", "x2"], "predictor")],
    )
    assert form.data.shape == (2, 3)
    assert list(form.labels["component"]) == ["CCA1", "CCA2"]
    np.testing.assert_allclose(
        export["eigenvalues"], [0.07592386857218954, 0.00012917276722056823],
        rtol=0, atol=1e-12,
    )
    assert export["total_inertia"] == pytest.approx(0.15765814626171162, abs=1e-12)
    assert export["constrained_inertia"] == pytest.approx(0.0760530413394101, abs=1e-12)
    assert export["unconstrained_inertia"] == pytest.approx(0.08160510492230152, abs=1e-12)
    assert export["constrained_fraction"] == pytest.approx(
        0.0760530413394101 / 0.15765814626171162, abs=1e-12
    )
    site = np.asarray(export["site_scores"])
    species = np.asarray(export["species_scores"])
    assert site.shape == (8, 2)
    assert species.shape == (3, 2)
    np.testing.assert_allclose((site**2).sum(axis=0), [1.0, 1.0], atol=1e-10)
    np.testing.assert_allclose((species**2).sum(axis=0), [1.0, 1.0], atol=1e-10)


def test_cca_rejects_invalid_inputs():
    bad = Y.copy()
    bad[0, 0] = -1
    with pytest.raises(StepError, match="nonnegative"):
        _run(CcaStep(), {"output": "c"}, [_table_form(bad, ["a", "b", "c"]), _table_form(X, ["x1", "x2"], "predictor")])
    bad = Y.copy()
    bad[0, :] = 0
    with pytest.raises(StepError, match="positive margin"):
        _run(CcaStep(), {"output": "c"}, [_table_form(bad, ["a", "b", "c"]), _table_form(X, ["x1", "x2"], "predictor")])
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            CcaStep(),
            {"output": "c"},
            [
                _table_form(Y, ["a", "b", "c"]),
                _table_form(np.ones((8, 1)), ["x1"], "predictor"),
            ],
        )


def test_cca_rejects_mismatched_samples():
    response = _table_form(Y, ["a", "b", "c"])
    predictor = _table_form(X, ["x1", "x2"], "predictor")
    predictor.labels["sample"] = {f"z{i}": i for i in range(8)}
    predictor.labels["sample"].update({"z0": 0})
    with pytest.raises(StepError, match="samples must match"):
        _run(CcaStep(), {"output": "c"}, [response, predictor])
