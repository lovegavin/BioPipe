"""Tests for the 1.11.0 statistics and species-pool operators."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.periodogram import PeriodogramStep
from src.task.step.steps.specpool import SpecpoolStep
from src.task.step.steps.turning_point import TurningPointStep
from src.task.step.steps.weighted_kappa import WeightedKappaStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _labels(names):
    return {name: index for index, name in enumerate(names)}


RATING_1 = np.array([1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3])
RATING_2 = np.array([1, 2, 2, 1, 3, 3, 1, 2, 2, 1, 3, 3, 1, 2, 2, 1, 3, 2])


def _rating_form(first, second):
    data = np.column_stack([first, second])
    subjects = [f"s{index}" for index in range(data.shape[0])]
    return _form(data, ["subject", "rater"],
                 {"subject": _labels(subjects), "rater": {"a": 0, "b": 1}})


def test_weighted_kappa_linear_matches_irr():
    form = _rating_form(RATING_1, RATING_2)
    result, exported = _run(WeightedKappaStep(), {"weights": "linear"}, (form,))
    assert list(result.dims) == ["statistic", "value"]
    assert result.data[:, 0][0] == pytest.approx(0.55319148936170215, rel=1e-6)
    assert exported["kappa"] == pytest.approx(0.55319148936170215, rel=1e-6)
    names = ["kappa", "se", "z", "p_value", "n_subjects", "n_categories"]
    values = {name: float(result.data[index, 0]) for index, name in enumerate(names)}
    assert values["z"] == pytest.approx(3.0179106068831341, rel=1e-5)
    assert values["p_value"] == pytest.approx(0.0025452397274430272, rel=1e-4)
    assert values["n_subjects"] == 18
    assert values["n_categories"] == 3


def test_weighted_kappa_quadratic_matches_irr():
    form = _rating_form(RATING_1, RATING_2)
    result, exported = _run(WeightedKappaStep(), {"weights": "quadratic"}, (form,))
    assert exported["kappa"] == pytest.approx(0.69565217391304346, rel=1e-6)
    assert float(result.data[2, 0]) == pytest.approx(2.9616842512430201, rel=1e-5)


def test_weighted_kappa_rejects_bad_inputs():
    single = _form(np.ones((5, 2)), ["subject", "rater"],
                   {"subject": _labels([f"s{i}" for i in range(5)]),
                    "rater": {"a": 0, "b": 1}})
    with pytest.raises(StepError, match="two rating categories"):
        _run(WeightedKappaStep(), {}, (single,))
    three_raters = _form(np.ones((4, 3)), ["subject", "rater"],
                         {"subject": _labels([f"s{i}" for i in range(4)]),
                          "rater": {"a": 0, "b": 1, "c": 2}})
    with pytest.raises(StepError, match="exactly two raters"):
        _run(WeightedKappaStep(), {}, (three_raters,))


TURNING = np.array([1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 9, 7, 8, 10, 9, 11, 10])


def _series_form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    samples = [f"s{index}" for index in range(data.shape[0])]
    return _form(data, ["sample", "feature"],
                 {"sample": _labels(samples), "feature": {"value": 0}})


def test_turning_point_matches_randtests():
    result, exported = _run(TurningPointStep(), {"value_label": "value"},
                            (_series_form(TURNING),))
    assert list(result.dims) == ["test", "value"]
    row = result.data[0]
    assert row[0] == pytest.approx(2.5544268486485429, rel=1e-6)
    assert row[1] == 15
    assert row[2] == pytest.approx(0.010636277651039139, rel=1e-4)
    assert row[3] == 18
    assert exported["turning_points"] == 15


def test_turning_point_drops_consecutive_ties():
    values = [1, 1, 2, 3, 2, 4, 3, 5]
    result, exported = _run(TurningPointStep(), {"value_label": "value"},
                            (_series_form(values),))
    assert exported["n"] == 7
    assert exported["turning_points"] == 4
    expected_z = (4 - 2.0 * 5 / 3.0) / np.sqrt((16.0 * 7 - 29.0) / 90.0)
    assert float(result.data[0, 0]) == pytest.approx(expected_z, rel=1e-5)


PERIOD = np.array([1, 2, 1, 2, 1, 2, 1, 2, 9, 1, 2, 1])
R_FREQ = np.array([1 / 12, 2 / 12, 3 / 12, 4 / 12, 5 / 12, 6 / 12])
R_SPEC = np.array([4.8899576603592685, 5.3333333333333313, 4.083333333333333,
                   4.3333333333333321, 7.7767090063073967, 2.0833333333333326])


def test_periodogram_matches_spec_pgram():
    result, exported = _run(PeriodogramStep(), {"value_label": "value"},
                            (_series_form(PERIOD),))
    assert list(result.dims) == ["frequency", "statistic"]
    assert result.data.shape == (6, 2)
    assert result.data[:, 0] == pytest.approx(R_FREQ, rel=1e-6)
    assert result.data[:, 1] == pytest.approx(R_SPEC, rel=1e-6)
    assert exported["n_used"] == 12


def test_periodogram_detrend_removes_linear_trend():
    values = np.arange(1, 13, dtype=np.float64) * 2.0
    result, exported = _run(PeriodogramStep(), {"value_label": "value", "detrend": True},
                            (_series_form(values),))
    assert exported["detrend"] is True
    assert np.max(np.abs(result.data[:, 1])) < 1e-8
    with pytest.raises(StepError, match="at least four observations"):
        _run(PeriodogramStep(), {"value_label": "value"},
             (_series_form([1.0, 2.0, 3.0]),))


COMM = np.array([
    [10, 5, 1, 0, 0],
    [8, 4, 2, 1, 0],
    [12, 6, 0, 0, 0],
    [0, 3, 7, 2, 1],
    [0, 1, 5, 3, 2],
    [1, 0, 2, 6, 4],
], dtype=np.float64)
POOLS = ["A", "A", "A", "B", "B", "B"]


def _pool_forms():
    abundance = _form(COMM, ["sample", "taxon"],
                      {"sample": _labels([f"s{i}" for i in range(6)]),
                       "taxon": _labels([f"t{i}" for i in range(5)])})
    meta = _form(np.array([[0], [0], [0], [1], [1], [1]], dtype=np.float64),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]),
                  "feature": {"pool": 0}})
    return abundance, meta


R_SPECPOOL = {
    "Species": [4.0, 5.0],
    "chao": [4.333333333333333, 5.333333333333333],
    "chao.se": [0.94280904158206336, 0.94280904158206336],
    "jack1": [4.666666666666667, 5.666666666666667],
    "jack1.se": [0.66666666666666674, 0.66666666666666674],
    "jack2": [4.833333333333333, 5.833333333333333],
    "boot": [4.333333333333333, 5.333333333333333],
    "boot.se": [0.54433105395181736, 0.47140452079103173],
    "n": [3.0, 3.0],
}


def test_specpool_matches_vegan_values():
    abundance, meta = _pool_forms()
    result, exported = _run(SpecpoolStep(), {"group_label": "pool"},
                            (abundance, meta))
    assert list(result.dims) == ["pool", "statistic"]
    assert result.data.shape[0] == 2
    statistics = {name: index for index, name in enumerate(R_SPECPOOL)}
    for name, expected in R_SPECPOOL.items():
        column = statistics[name]
        assert result.data[:, column] == pytest.approx(expected, abs=1e-5)
    assert exported["pools"] == ["0", "1"]
    assert exported["species"] == [4, 5]


def test_specpool_smallsample_false_changes_only_chao():
    abundance, meta = _pool_forms()
    corrected, _ = _run(SpecpoolStep(), {"group_label": "pool", "smallsample": True},
                        (abundance, meta))
    plain, _ = _run(SpecpoolStep(), {"group_label": "pool", "smallsample": False},
                    (abundance, meta))
    chao = 1
    jack1 = 3
    assert corrected.data[:, chao] == pytest.approx(R_SPECPOOL["chao"], abs=1e-5)
    assert plain.data[:, chao][0] == pytest.approx(
        4.0 + 1 * 1 / 2, abs=1e-5)
    assert corrected.data[:, jack1] == pytest.approx(R_SPECPOOL["jack1"], abs=1e-5)
    assert plain.data[:, jack1] == pytest.approx(R_SPECPOOL["jack1"], abs=1e-5)


def test_specpool_rejects_unmatched_metadata():
    abundance, meta = _pool_forms()
    broken = _form(np.arange(5).reshape(-1, 1), ["sample", "feature"],
                   {"sample": _labels([f"x{i}" for i in range(5)]),
                    "feature": {"pool": 0}})
    with pytest.raises(StepError, match="have no 'pool' value"):
        _run(SpecpoolStep(), {"group_label": "pool"}, (abundance, broken))
