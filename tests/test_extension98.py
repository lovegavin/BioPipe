from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.task.step.steps.agostino_test import AgostinoTestStep
from src.task.step.steps.anscombe_test import AnscombeTestStep
from src.task.step.steps.mood_median import MoodMedianStep
from src.task.step.steps.var_test import VarTestStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    value = Form(np.asarray(data, dtype=dtype), list(dims), labels, {"missing_code": np.nan})
    value.validate()
    return value


def _run(step, params, inputs):
    params = {"output": "out", **params}
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _features(first, second):
    values = np.asarray(list(first) + list(second), dtype=np.float32).reshape(1, -1)
    names = [f"s{i}" for i in range(values.shape[1])]
    return _form(values, ["feature", "sample"], {"feature": {"value": 0}, "sample": {n: i for i, n in enumerate(names)}})


def _groups_meta(labels):
    names = [f"s{i}" for i in range(len(labels))]
    return _form(np.asarray(labels, dtype=object).reshape(-1, 1), ["sample", "feature"],
                 {"sample": {n: i for i, n in enumerate(names)}, "feature": {"group": 0}}, dtype=object)


def _series(values):
    data = np.asarray(values, dtype=np.float32).reshape(-1, 1)
    return _form(data, ["sample", "feature"], {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {"value": 0}})


def test_mood_matches_r_values():
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    features = _features(x, y)
    meta = _groups_meta([0] * len(x) + [1] * len(y))
    out, export = _run(MoodMedianStep(), {"group_label": "group"}, [features, meta])
    assert list(out.labels["statistic"]) == ["Z", "p_value", "n_x", "n_y"]
    assert out.data[0, 0] == pytest.approx(-1.0544701613375884, abs=1e-5)
    assert out.data[0, 1] == pytest.approx(0.29166771478283576, abs=1e-6)
    assert out.data[0, 2] == pytest.approx(10.0)
    assert out.data[0, 3] == pytest.approx(10.0)
    assert export["groups"] in ([0, 1], ["0", "1"])


def test_mood_ties_match_r_values():
    x = [1, 2, 3, 4, 5, 6]
    y = [1, 2, 3, 4, 5, 100]
    features = _features(x, y)
    meta = _groups_meta([0] * 6 + [1] * 6)
    out, _ = _run(MoodMedianStep(), {"group_label": "group"}, [features, meta])
    assert out.data[0, 0] == pytest.approx(-0.29070839447937247, abs=1e-5)
    assert out.data[0, 1] == pytest.approx(0.77127435089028651, abs=1e-6)


def test_mood_alternative_directions():
    x = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
    features = _features(x, y)
    meta = _groups_meta([0] * 10 + [1] * 10)
    less, _ = _run(MoodMedianStep(), {"group_label": "group", "alternative": "less"}, [features, meta])
    greater, _ = _run(MoodMedianStep(), {"group_label": "group", "alternative": "greater"}, [features, meta])
    assert less.data[0, 1] + greater.data[0, 1] == pytest.approx(1.0, abs=1e-6)
    assert less.data[0, 1] == pytest.approx(0.14583385739141788, abs=1e-6)


def test_mood_rejects_bad_shapes():
    features = _features([1, 2, 3], [10, 20, 30])
    meta = _groups_meta([0, 1, 2])
    with pytest.raises(StepError):
        _run(MoodMedianStep(), {"group_label": "group"}, [features, meta])
    single = _features([1], [2])
    meta2 = _groups_meta([0, 1])
    with pytest.raises(StepError):
        _run(MoodMedianStep(), {"group_label": "group"}, [single, meta2])


def test_var_test_matches_r_values():
    x = [1, 2, 3, 4, 5, 6]
    y = [2, 4, 6, 8, 10, 12]
    features = _features(x, y)
    meta = _groups_meta([0] * 6 + [1] * 6)
    out, _ = _run(VarTestStep(), {"group_label": "group"}, [features, meta])
    assert list(out.labels["statistic"]) == ["F", "df1", "df2", "p_value", "ci_low", "ci_high"]
    assert out.data[0, 0] == pytest.approx(0.25, rel=1e-5)
    assert out.data[0, 1] == pytest.approx(5.0)
    assert out.data[0, 2] == pytest.approx(5.0)
    assert out.data[0, 3] == pytest.approx(0.15437725048441334, rel=1e-5)
    assert out.data[0, 4] == pytest.approx(0.034982737557465352, rel=1e-4)
    assert out.data[0, 5] == pytest.approx(1.7865954571832061, rel=1e-4)


def test_var_test_alternative_and_confidence():
    x = [1, 2, 3, 4, 5, 6]
    y = [2, 4, 6, 8, 10, 12]
    features = _features(x, y)
    meta = _groups_meta([0] * 6 + [1] * 6)
    less, _ = _run(VarTestStep(), {"group_label": "group", "alternative": "less"}, [features, meta])
    greater, _ = _run(VarTestStep(), {"group_label": "group", "alternative": "greater"}, [features, meta])
    assert less.data[0, 3] == pytest.approx(0.07718862524220667, rel=1e-5)
    assert greater.data[0, 3] == pytest.approx(1.0 - 0.07718862524220667, rel=1e-5)
    wide, _ = _run(VarTestStep(), {"group_label": "group", "conf_level": 0.9}, [features, meta])
    assert wide.data[0, 4] > 0.04
    assert wide.data[0, 5] < 1.78


def test_var_test_rejects_degenerate_samples():
    features = _features([1, 2, 3], [4, 5, 6])
    meta = _groups_meta([0, 0, 1])
    with pytest.raises(StepError):
        _run(VarTestStep(), {"group_label": "group"}, [features, meta])
    flat = _features([5, 5, 5], [1, 2, 3])
    meta2 = _groups_meta([0, 0, 0, 1, 1, 1])
    with pytest.raises(StepError):
        _run(VarTestStep(), {"group_label": "group"}, [flat, meta2])


def test_agostino_matches_r_values():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30]
    out, export = _run(AgostinoTestStep(), {"value_label": "value", "output": "out"}, [_series(values)])
    assert list(out.labels["value"]) == ["skewness", "z", "p_value", "n"]
    assert out.data[0, 0] == pytest.approx(1.6122579953295555, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(2.7223309730674288, rel=1e-5)
    assert out.data[0, 2] == pytest.approx(0.0064823184633833039, rel=1e-5)
    assert export["n"] == 12


def test_agostino_secondary_fixture():
    values = [1.2, 2.1, 2.9, 3.5, 3.9, 4.2, 4.6, 5.1, 5.4, 5.9, 6.3, 6.8]
    out, export = _run(AgostinoTestStep(), {"value_label": "value"}, [_series(values)])
    assert out.data[0, 0] == pytest.approx(-0.3175828190107205, rel=1e-5)
    assert out.data[0, 1] == pytest.approx(-0.59705481693607743, rel=1e-5)
    assert out.data[0, 2] == pytest.approx(0.55047078284937978, rel=1e-6)
    assert export["statistic"] == pytest.approx(-0.59705481693607743, rel=1e-6)


def test_anscombe_matches_r_values():
    values = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30]
    out, export = _run(AnscombeTestStep(), {"value_label": "value", "output": "out"}, [_series(values)])
    assert list(out.labels["value"]) == ["kurtosis", "z", "p_value", "n"]
    assert out.data[0, 0] == pytest.approx(4.6492457866401962, rel=1e-6)
    assert out.data[0, 1] == pytest.approx(2.0728109528803347, rel=1e-6)
    assert out.data[0, 2] == pytest.approx(0.038189876705648086, rel=1e-5)
    assert export["kurtosis"] == pytest.approx(4.6492457866401962, rel=1e-6)


def test_anscombe_secondary_fixture():
    values = [1.2, 2.1, 2.9, 3.5, 3.9, 4.2, 4.6, 5.1, 5.4, 5.9, 6.3, 6.8]
    out, _ = _run(AnscombeTestStep(), {"value_label": "value"}, [_series(values)])
    assert out.data[0, 0] == pytest.approx(2.1741075018709135, rel=1e-5)
    assert out.data[0, 1] == pytest.approx(-0.35142579103041294, rel=1e-5)
    assert out.data[0, 2] == pytest.approx(0.72526893631151101, rel=1e-6)


def test_moment_tests_reject_bad_samples():
    with pytest.raises(StepError):
        _run(AgostinoTestStep(), {"value_label": "value"}, [_series([1, 2, 3])])
    with pytest.raises(StepError):
        _run(AnscombeTestStep(), {"value_label": "value"}, [_series([3] * 10)])
