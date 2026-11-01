"""Tests for the 1.17.0 gower, PAM and Nelson-Aalen additions."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.gower_distance import GowerDistanceStep
from src.task.step.steps.nelson_aalen import NelsonAalenStep
from src.task.step.steps.pam import PamStep

GOWER = np.asarray([
    [1.0, 10.0, 0.0],
    [2.0, 12.0, 0.0],
    [3.5, 9.0, 1.0],
    [4.0, 15.0, 1.0],
    [6.0, 20.0, 2.0],
    [7.5, 18.0, 2.0],
], dtype=np.float64)

GOWER_LOWER = [
    0.11188811188811187, 0.49184149184149178, 0.63869463869463872,
    0.89277389277389274, 0.90909090909090917, 0.50116550116550118,
    0.52680652680652684, 0.78088578088578087, 0.79720279720279719,
    0.20745920745920743, 0.79487179487179482, 0.81118881118881125,
    0.58741258741258739, 0.60372960372960371, 0.13752913752913751,
]

GOWER_CONST = [
    0.083916083916083906, 0.368881118881118852, 0.479020979020979010,
    0.669580419580419584, 0.681818181818181879, 0.375874125874125886,
    0.395104895104895104, 0.585664335664335622, 0.597902097902097918,
    0.155594405594405572, 0.596153846153846145, 0.608391608391608441,
    0.440559440559440574, 0.452797202797202814, 0.103146853146853124,
]

GOWER_NA = [
    0.090909090909090898, 0.491841491841491785, 0.638694638694638717,
    0.892773892773892741, 0.909090909090909172, 0.636363636363636354,
    0.636363636363636354, 0.863636363636363646, 0.772727272727272707,
    0.207459207459207429, 0.794871794871794823, 0.811188811188811254,
    0.587412587412587395, 0.603729603729603714, 0.137529137529137507,
]

PAM_POINTS = np.asarray([
    [0.0, 0.0],
    [0.3, 0.2],
    [1.0, 1.2],
    [1.2, 0.9],
    [5.0, 5.0],
    [5.4, 4.7],
    [8.0, 1.0],
    [8.3, 1.4],
], dtype=np.float64)

SURVIVAL = [
    (2.0, 1.0), (3.0, 0.0), (5.0, 1.0), (5.0, 1.0),
    (6.0, 0.0), (8.0, 1.0), (10.0, 0.0), (12.0, 1.0),
]

NA_TIMES = [2.0, 3.0, 5.0, 6.0, 8.0, 10.0, 12.0]
NA_N_RISK = [8.0, 7.0, 6.0, 4.0, 3.0, 2.0, 1.0]
NA_N_EVENT = [1.0, 0.0, 2.0, 0.0, 1.0, 0.0, 1.0]
NA_CUMHAZ = [0.125, 0.125, 0.49166666666666664, 0.49166666666666664,
             0.82499999999999996, 0.82499999999999996, 1.82499999999999996]
NA_SE = [0.125, 0.125, 0.28879539085272427, 0.28879539085272427,
         0.44103728741330805, 0.44103728741330805, 1.09293819079071852]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float64), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _square_expectation(values, n=6):
    matrix = np.zeros((n, n), dtype=np.float64)
    positions = np.triu_indices(n, 1)
    matrix[positions] = values
    matrix[(positions[1], positions[0])] = values
    return matrix


def _clinical(rows):
    data = np.asarray(rows, dtype=np.float64)
    return _form(data, ["sample", "feature"],
                 {"sample": {f"s{i}": i for i in range(data.shape[0])},
                  "feature": {"time": 0, "status": 1}})


def test_gower_matches_daisy_lower_triangle():
    labels = {"sample": {f"s{i}": i for i in range(6)},
              "feature": {"a": 0, "b": 1, "g": 2}}
    form = _form(GOWER, ["sample", "feature"], labels)
    out, export = _run(GowerDistanceStep(), [form], {"categorical_labels": ["g"]})
    assert out.dims == ["sample", "sample_b"]
    expected = _square_expectation(GOWER_LOWER)
    np.testing.assert_allclose(out.data, expected, atol=1e-7, rtol=1e-7)
    assert np.allclose(np.diag(out.data), 0.0)
    assert export["categorical_features"] == ["g"]
    assert export["numeric_features"] == ["a", "b"]


def test_gower_constant_column_counts_with_zero_contribution():
    data = np.column_stack([GOWER, np.ones(6)])
    labels = {"sample": {f"s{i}": i for i in range(6)},
              "feature": {"a": 0, "b": 1, "g": 2, "const": 3}}
    form = _form(data, ["sample", "feature"], labels)
    out, _ = _run(GowerDistanceStep(), [form], {"categorical_labels": ["g"]})
    np.testing.assert_allclose(out.data, _square_expectation(GOWER_CONST),
                               atol=1e-7, rtol=1e-7)


def test_gower_missing_values_are_reweighted():
    data = GOWER.copy()
    data[1, 0] = np.nan
    labels = {"sample": {f"s{i}": i for i in range(6)},
              "feature": {"a": 0, "b": 1, "g": 2}}
    form = _form(data, ["sample", "feature"], labels)
    out, _ = _run(GowerDistanceStep(), [form], {"categorical_labels": ["g"]})
    np.testing.assert_allclose(out.data, _square_expectation(GOWER_NA),
                               atol=1e-7, rtol=1e-7)


def test_gower_rejects_unknown_categorical_label_and_single_sample():
    labels = {"sample": {f"s{i}": i for i in range(6)},
              "feature": {"a": 0, "b": 1, "g": 2}}
    form = _form(GOWER, ["sample", "feature"], labels)
    with pytest.raises(StepError, match="categorical label"):
        _run(GowerDistanceStep(), [form], {"categorical_labels": ["missing"]})
    single = _form(GOWER[:1], ["sample", "feature"],
                   {"sample": {"s0": 0}, "feature": labels["feature"]})
    with pytest.raises(StepError, match="at least two samples"):
        _run(GowerDistanceStep(), [single], {"categorical_labels": ["g"]})


def test_nelson_aalen_matches_survfit_fh():
    form = _clinical(SURVIVAL)
    out, export = _run(NelsonAalenStep(), [form],
                       {"time_label": "time", "event_label": "status"})
    assert out.dims == ["time", "statistic"]
    assert export["times"] == NA_TIMES
    assert list(out.labels["statistic"]) == ["n_risk", "n_event", "cumhaz", "se"]
    np.testing.assert_allclose(out.data[:, 0], NA_N_RISK, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 1], NA_N_EVENT, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], NA_CUMHAZ, atol=1e-6)
    np.testing.assert_allclose(out.data[:, 3], NA_SE, atol=1e-6)


def test_nelson_aalen_errors():
    form = _clinical(SURVIVAL)
    with pytest.raises(StepError, match="clinical column"):
        _run(NelsonAalenStep(), [form], {"time_label": "missing", "event_label": "status"})
    censored = _clinical([(1.0, 0.0), (2.0, 0.0)])
    with pytest.raises(StepError, match="no events observed"):
        _run(NelsonAalenStep(), [censored], {"time_label": "time", "event_label": "status"})


def test_pam_two_clusters_matches_ripleys_pam():
    labels = {"sample": {f"s{i}": i for i in range(8)},
              "feature": {"x": 0, "y": 1}}
    form = _form(PAM_POINTS, ["sample", "feature"], labels)
    out, export = _run(PamStep(), [form], {"n_clusters": 2})
    assert out.dims == ["sample", "statistic"]
    np.testing.assert_allclose(out.data[:, 0], [1, 1, 1, 1, 2, 2, 2, 2], atol=1e-6)
    assert export["medoids"] == [1, 5]
    assert export["medoid_labels"] == ["s1", "s5"]
    assert export["build_objective"] == pytest.approx(1.5520093377226627, rel=1e-9)
    assert export["objective"] == pytest.approx(1.5170912829193339, rel=1e-9)
    assert out.data[:, 1] == pytest.approx(
        np.array([0.36055513, 0.0, 1.22065556, 1.14017543,
                  0.5, 0.0, 4.52220566, 4.39319619]), rel=1e-5)


def test_pam_three_clusters_matches_ripleys_pam():
    labels = {"sample": {f"s{i}": i for i in range(8)},
              "feature": {"x": 0, "y": 1}}
    form = _form(PAM_POINTS, ["sample", "feature"], labels)
    out, export = _run(PamStep(), [form], {"n_clusters": 3})
    np.testing.assert_allclose(out.data[:, 0], [1, 1, 1, 1, 2, 2, 3, 3], atol=1e-6)
    assert export["medoids"] == [1, 5, 7]
    assert export["objective"] == pytest.approx(0.46517326427736344, rel=1e-9)


def test_pam_rejects_invalid_arguments():
    labels = {"sample": {f"s{i}": i for i in range(8)},
              "feature": {"x": 0, "y": 1}}
    form = _form(PAM_POINTS, ["sample", "feature"], labels)
    with pytest.raises(StepError, match="n_clusters must satisfy"):
        _run(PamStep(), [form], {"n_clusters": 1})
    with pytest.raises(StepError, match="n_clusters must satisfy"):
        _run(PamStep(), [form], {"n_clusters": 8})
    bad = PAM_POINTS.copy()
    bad[0, 0] = np.nan
    with pytest.raises(StepError, match="missing or infinite"):
        _run(PamStep(), [_form(bad, ["sample", "feature"], labels)], {"n_clusters": 2})
