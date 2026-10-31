"""Hand checks for 0.83 db-RDA and leave-one-out meta-analysis."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.dbrda import DbrdaStep
from src.task.step.steps.leave_one_out import LeaveOneOutStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


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
EFFECT = np.array(
    [0.4629, 0.6535, 0.4254, 0.3927, 0.4661, -0.6996, -0.3884, 1.0418]
)
VARIANCE = np.array(
    [0.1281, 0.1528, 0.0869, 0.0809, 0.2528, 0.1163, 0.1557, 0.1949]
)


def test_dbrda_matches_vegan():
    export, form = _run(
        DbrdaStep(),
        {"n_components": 2, "output": "dbrda"},
        [
            _table_form(Y, ["sp1", "sp2", "sp3"]),
            _table_form(X, ["x1", "x2"], "predictor"),
        ],
    )
    assert form.data.shape == (2, 3)
    assert list(form.labels["component"]) == ["dbRDA1", "dbRDA2"]
    assert list(form.labels["statistic"]) == ["eigenvalue", "explained", "cumulative"]
    assert export["total_inertia"] == pytest.approx(0.29766435057928425, abs=1e-12)
    assert export["constrained_inertia"] == pytest.approx(
        0.14785322587790678, abs=1e-12
    )
    assert export["unconstrained_inertia"] == pytest.approx(
        0.14981112470137747, abs=1e-12
    )
    np.testing.assert_allclose(
        export["eigenvalues"],
        [0.14271793573379188, 0.0051352901441149134],
        rtol=0,
        atol=1e-12,
    )
    np.testing.assert_allclose(
        export["cumulative"],
        np.cumsum(
            np.array([0.14271793573379188, 0.0051352901441149134])
            / 0.29766435057928425
        ),
        rtol=0,
        atol=1e-12,
    )
    assert export["constrained_fraction"] == pytest.approx(
        0.14785322587790678 / 0.29766435057928425, abs=1e-12
    )


def test_dbrda_rejects_invalid_inputs():
    bad = Y.copy()
    bad[0, 0] = -1
    with pytest.raises(StepError, match="nonnegative"):
        _run(
            DbrdaStep(),
            {"output": "d"},
            [
                _table_form(bad, ["a", "b", "c"]),
                _table_form(X, ["x1", "x2"], "predictor"),
            ],
        )
    bad = Y.copy()
    bad[0, :] = 0
    with pytest.raises(StepError, match="positive response sum"):
        _run(
            DbrdaStep(),
            {"output": "d"},
            [
                _table_form(bad, ["a", "b", "c"]),
                _table_form(X, ["x1", "x2"], "predictor"),
            ],
        )
    with pytest.raises(StepError, match="rank deficient"):
        _run(
            DbrdaStep(),
            {"output": "d"},
            [
                _table_form(Y, ["a", "b", "c"]),
                _table_form(np.ones((8, 1)), ["x1"], "predictor"),
            ],
        )


def test_dbrda_rejects_mismatched_samples():
    response = _table_form(Y, ["a", "b", "c"])
    predictor = _table_form(X, ["x1", "x2"], "predictor")
    predictor.labels["sample"] = {f"z{i}": i for i in range(8)}
    with pytest.raises(StepError, match="samples must match"):
        _run(DbrdaStep(), {"output": "d"}, [response, predictor])


def test_leave_one_out_matches_metafor():
    export, form = _run(
        LeaveOneOutStep(),
        {
            "study_dim": "sample", "effect_label": "yi",
            "variance_label": "vi",
            "method": "random",
            "output": "loo",
        },
        [_table_form(np.column_stack([EFFECT, VARIANCE]), ["yi", "vi"])],
    )
    assert form.data.shape == (8, 11)
    assert list(form.labels["statistic"]) == [
        "estimate",
        "se",
        "z",
        "p",
        "ci_low",
        "ci_high",
        "tau2",
        "I2",
        "Q",
        "Qp",
        "k",
    ]
    assert [row["omitted"] for row in export["results"]] == [f"s{i}" for i in range(8)]
    first = export["results"][0]
    assert first["estimate"] == pytest.approx(0.24783622694697988, abs=1e-12)
    assert first["se"] == pytest.approx(0.22256015182479655, abs=1e-12)
    assert first["tau2"] == pytest.approx(0.20666323998000977, abs=1e-12)
    assert first["I2"] == pytest.approx(61.110175583952945, abs=1e-12)
    assert first["Q"] == pytest.approx(15.428200281419191, abs=1e-12)
    assert first["k"] == 7
    last = export["results"][-1]
    assert last["estimate"] == pytest.approx(0.18357359524663203, abs=1e-12)
    assert last["se"] == pytest.approx(0.19373951561949584, abs=1e-12)


def test_leave_one_out_fixed_effect():
    export, form = _run(
        LeaveOneOutStep(),
        {
            "study_dim": "sample", "effect_label": "yi",
            "variance_label": "vi",
            "method": "fixed",
            "output": "loo",
        },
        [_table_form(np.column_stack([EFFECT, VARIANCE]), ["yi", "vi"])],
    )
    first = export["results"][0]
    assert first["estimate"] == pytest.approx(0.23303691756346831, abs=1e-12)
    assert first["se"] == pytest.approx(0.13543160584780461, abs=1e-12)
    assert first["tau2"] == 0.0
    assert form.data[0, 6] == 0.0


def test_leave_one_out_confidence_interval():
    export, _ = _run(
        LeaveOneOutStep(),
        {
            "study_dim": "sample", "effect_label": "yi",
            "variance_label": "vi",
            "method": "fixed",
            "confidence": 0.90,
            "output": "loo",
        },
        [_table_form(np.column_stack([EFFECT, VARIANCE]), ["yi", "vi"])],
    )
    narrower, _ = _run(
        LeaveOneOutStep(),
        {
            "study_dim": "sample", "effect_label": "yi",
            "variance_label": "vi",
            "method": "fixed",
            "confidence": 0.95,
            "output": "loo",
        },
        [_table_form(np.column_stack([EFFECT, VARIANCE]), ["yi", "vi"])],
    )
    width_90 = export["results"][0]["ci_high"] - export["results"][0]["ci_low"]
    width_95 = narrower["results"][0]["ci_high"] - narrower["results"][0]["ci_low"]
    assert width_90 < width_95


def test_leave_one_out_rejects_invalid_inputs():
    with pytest.raises(StepError, match="variances must be positive"):
        _run(
            LeaveOneOutStep(),
            {"study_dim": "sample", "effect_label": "yi", "variance_label": "vi", "output": "loo"},
            [
                _table_form(
                    np.column_stack([EFFECT, np.where(np.arange(8) == 0, -1, VARIANCE)]),
                    ["yi", "vi"],
                )
            ],
        )
    with pytest.raises(StepError, match="at least three studies"):
        _run(
            LeaveOneOutStep(),
            {"study_dim": "sample", "effect_label": "yi", "variance_label": "vi", "output": "loo"},
            [_table_form(np.column_stack([EFFECT[:2], VARIANCE[:2]]), ["yi", "vi"])],
        )
    with pytest.raises(StepError, match="must differ"):
        _run(
            LeaveOneOutStep(),
            {"study_dim": "sample", "effect_label": "yi", "variance_label": "yi", "output": "loo"},
            [_table_form(np.column_stack([EFFECT, VARIANCE]), ["yi", "vi"])],
        )
