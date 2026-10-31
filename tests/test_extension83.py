"""Hand checks for 0.91 NMDS."""
from __future__ import annotations

import numpy as np
import pytest
from scipy.spatial.distance import cdist, pdist

from src.core import Form, StepError
from src.task.step.steps.nmds import NmdsStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _distance_form(points):
    points = np.asarray(points, dtype=float)
    D = cdist(points, points)
    labels = {f"s{i}": i for i in range(points.shape[0])}
    form = Form(
        data=D,
        dims=["sample", "sample_b"],
        labels={"sample": labels, "sample_b": dict(labels)},
        info={},
    )
    form.validate()
    return form


def test_nmds_recovers_euclidean_layout():
    points = np.array(
        [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]
    )
    export, out = _run(
        NmdsStep(),
        {"n_components": 2, "max_iter": 500, "output": "nmds"},
        _distance_form(points),
    )
    assert out.dims == ["sample", "component"]
    assert out.data.shape == (6, 2)
    assert out.labels["component"] == {"NMDS1": 0, "NMDS2": 1}
    assert out.info["metric"] is False
    assert out.info["n"] == 6
    assert out.info["n_components"] == 2
    assert export["stress1"] < 1e-8
    observed = pdist(out.data)
    expected = pdist(points)
    assert np.corrcoef(observed, expected)[0, 1] > 0.999


def test_nmds_one_dimensional_ordering():
    points = np.array([[0.0], [1.0], [3.0], [6.0], [10.0]])
    export, out = _run(
        NmdsStep(),
        {"n_components": 1, "max_iter": 500},
        _distance_form(points),
    )
    assert out.data.shape == (5, 1)
    assert out.labels["component"] == {"NMDS1": 0}
    assert export["stress1"] < 1e-8
    coords = out.data[:, 0]
    assert np.all(np.diff(coords) > 0) or np.all(np.diff(coords) < 0)


def test_nmds_is_deterministic():
    points = np.array(
        [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]
    )
    form = _distance_form(points)
    first, first_out = _run(NmdsStep(), {"n_components": 2}, form)
    second, second_out = _run(NmdsStep(), {"n_components": 2}, form)
    np.testing.assert_allclose(first_out.data, second_out.data, rtol=0, atol=1e-12)
    assert first["stress"] == second["stress"]
    assert first["n_iter"] == second["n_iter"]


def test_nmds_invalid_distance_matrices():
    with pytest.raises(StepError, match="square"):
        form = Form(
            data=np.zeros((3, 2)),
            dims=["sample", "sample_b"],
            labels={"sample": {"a": 0, "b": 1, "c": 2}, "sample_b": {"a": 0, "b": 1}},
            info={},
        )
        NmdsStep().run(Ctx({}), [form])
    with pytest.raises(StepError, match="symmetric"):
        form = Form(
            data=np.array([[0.0, 1.0, 2.0], [1.0, 0.0, 1.0], [3.0, 1.0, 0.0]]),
            dims=["sample", "sample_b"],
            labels={
                "sample": {"a": 0, "b": 1, "c": 2},
                "sample_b": {"a": 0, "b": 1, "c": 2},
            },
            info={},
        )
        NmdsStep().run(Ctx({}), [form])
    with pytest.raises(StepError, match="nonnegative"):
        form = Form(
            data=np.array([[0.0, -1.0, 1.0], [-1.0, 0.0, 1.0], [1.0, 1.0, 0.0]]),
            dims=["sample", "sample_b"],
            labels={
                "sample": {"a": 0, "b": 1, "c": 2},
                "sample_b": {"a": 0, "b": 1, "c": 2},
            },
            info={},
        )
        NmdsStep().run(Ctx({}), [form])
    with pytest.raises(StepError, match="diagonal"):
        form = Form(
            data=np.array([[1.0, 1.0, 1.0], [1.0, 0.0, 1.0], [1.0, 1.0, 0.0]]),
            dims=["sample", "sample_b"],
            labels={
                "sample": {"a": 0, "b": 1, "c": 2},
                "sample_b": {"a": 0, "b": 1, "c": 2},
            },
            info={},
        )
        NmdsStep().run(Ctx({}), [form])
    with pytest.raises(StepError, match="positive distances"):
        form = Form(
            data=np.zeros((3, 3)),
            dims=["sample", "sample_b"],
            labels={
                "sample": {"a": 0, "b": 1, "c": 2},
                "sample_b": {"a": 0, "b": 1, "c": 2},
            },
            info={},
        )
        NmdsStep().run(Ctx({}), [form])
    with pytest.raises(StepError, match="n_components"):
        NmdsStep().run(Ctx({"n_components": 4}), [_distance_form(points=[
            [0.0], [1.0], [2.0], [3.0]
        ])])
