"""R oracle checks for the 1.13.0 scale, variance and moment tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.agostino_test import AgostinoTestStep
from src.task.step.steps.anscombe_test import AnscombeTestStep
from src.task.step.steps.mood_median import MoodMedianStep
from src.task.step.steps.var_test import VarTestStep

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript is required")

MOOD_X = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
MOOD_Y = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]
VAR_X = [1, 2, 3, 4, 5, 6]
VAR_Y = [2, 4, 6, 8, 10, 12]
MOMENT_X = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 20, 30]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    out = Form(np.asarray(data, dtype=dtype), list(dims), labels, {"missing_code": np.nan})
    out.validate()
    return out


def _pair_forms(first, second):
    values = np.asarray(list(first) + list(second), dtype=np.float32).reshape(1, -1)
    names = [f"s{index}" for index in range(values.shape[1])]
    features = _form(values, ["feature", "sample"],
                     {"feature": {"value": 0}, "sample": {name: index for index, name in enumerate(names)}})
    groups = np.asarray([0] * len(first) + [1] * len(second), dtype=object).reshape(-1, 1)
    meta = _form(groups, ["sample", "feature"],
                 {"sample": {name: index for index, name in enumerate(names)},
                  "feature": {"group": 0}}, dtype=object)
    return [features, meta]


def _series(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    samples = [f"s{index}" for index in range(data.shape[0])]
    return _form(data, ["sample", "feature"],
                 {"sample": {name: index for index, name in enumerate(samples)},
                  "feature": {"value": 0}})


def _run(step, inputs, params=None):
    ctx = Ctx(params or {"value_label": "value", "output": "out"})
    step.run(ctx, inputs)
    return ctx["out"]


def _join(values):
    return "c(" + ", ".join(repr(float(value)) for value in values) + ")"


R_CODE = f"""
suppressMessages(library(moments))
m <- stats::mood.test({_join(MOOD_X)}, {_join(MOOD_Y)})
cat(sprintf("MOOD %.17g %.17g\\n", m$statistic, m$p.value))
v <- stats::var.test({_join(VAR_X)}, {_join(VAR_Y)})
cat(sprintf("VAR %.17g %.17g %.17g %.17g %.17g %.17g\\n", v$statistic, v$parameter[1], v$parameter[2],
            v$p.value, v$conf.int[1], v$conf.int[2]))
a <- moments::agostino.test({_join(MOMENT_X)})
cat(sprintf("AGOSTINO %.17g %.17g %.17g\\n", a$statistic["skew"], a$statistic["z"], a$p.value))
b <- moments::anscombe.test({_join(MOMENT_X)})
cat(sprintf("ANSCOMBE %.17g %.17g %.17g\\n", b$statistic["kurt"], b$statistic["z"], b$p.value))
"""


def _oracle():
    result = subprocess.run(["Rscript", "-e", R_CODE], capture_output=True, text=True,
                            check=True, timeout=180)
    values = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            values[parts[0]] = [float(part) for part in parts[1:]]
    return values


def test_scale_variance_and_moment_tests_match_r():
    oracle = _oracle()

    mood = _run(MoodMedianStep(), _pair_forms(MOOD_X, MOOD_Y), {"group_label": "group", "output": "out"})
    assert mood.data[0, 0] == pytest.approx(oracle["MOOD"][0], abs=1e-5)
    assert mood.data[0, 1] == pytest.approx(oracle["MOOD"][1], abs=1e-6)

    var = _run(VarTestStep(), _pair_forms(VAR_X, VAR_Y), {"group_label": "group", "output": "out"})
    assert var.data[0, 0] == pytest.approx(oracle["VAR"][0], rel=1e-5)
    assert var.data[0, 1] == pytest.approx(oracle["VAR"][1])
    assert var.data[0, 2] == pytest.approx(oracle["VAR"][2])
    assert var.data[0, 3] == pytest.approx(oracle["VAR"][3], rel=1e-5)
    assert var.data[0, 4] == pytest.approx(oracle["VAR"][4], rel=1e-4)
    assert var.data[0, 5] == pytest.approx(oracle["VAR"][5], rel=1e-4)

    agostino = _run(AgostinoTestStep(), [_series(MOMENT_X)])
    assert agostino.data[0, 0] == pytest.approx(oracle["AGOSTINO"][0], rel=1e-6)
    assert agostino.data[0, 1] == pytest.approx(oracle["AGOSTINO"][1], rel=1e-6)
    assert agostino.data[0, 2] == pytest.approx(oracle["AGOSTINO"][2], rel=1e-6)

    anscombe = _run(AnscombeTestStep(), [_series(MOMENT_X)])
    assert anscombe.data[0, 0] == pytest.approx(oracle["ANSCOMBE"][0], rel=1e-6)
    assert anscombe.data[0, 1] == pytest.approx(oracle["ANSCOMBE"][1], rel=1e-6)
    assert anscombe.data[0, 2] == pytest.approx(oracle["ANSCOMBE"][2], rel=1e-6)
