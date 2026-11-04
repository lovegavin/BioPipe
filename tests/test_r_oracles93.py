"""R oracle checks for the 1.12.0 normality and trend operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cox_stuart import CoxStuartStep
from src.task.step.steps.lilliefors_test import LillieforsTestStep
from src.task.step.steps.pearson_test import PearsonTestStep
from src.task.step.steps.rank_test import RankTestStep

pytestmark = pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript is required")

LILLIE_X = [0.13, 0.25, 0.31, 0.44, 0.52, 0.61, 0.72, 0.81, 0.92, 1.05]
COX_X = [1, 5, 2, 8, 3, 9, 4, 10, 6, 11, 7, 12]
RANK_X = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5, 8, 9, 7, 9, 3]
PEARSON_X = [-1.2, -0.5, -0.3, -0.1, 0.0, 0.2, 0.4, 0.6, 0.9, 1.1,
             1.4, 1.7, 2.0, 2.4, 2.9, 3.3, 3.9, 4.6, 5.5, 7.0]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    samples = [f"s{index}" for index in range(data.shape[0])]
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["sample", "feature"],
        labels={"sample": {name: index for index, name in enumerate(samples)},
                "feature": {"value": 0}},
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _run(step, values):
    ctx = Ctx({"value_label": "value", "output": "out"})
    step.run(ctx, (_form(values),))
    return ctx["out"]


def _join(values):
    return "c(" + ", ".join(repr(float(value)) for value in values) + ")"


R_CODE = f"""
suppressMessages(library(nortest))
suppressMessages(library(randtests))
l <- nortest::lillie.test({_join(LILLIE_X)})
cat(sprintf("LILLIE %.17g %.17g\\n", l$statistic, l$p.value))
c1 <- randtests::cox.stuart.test({_join(COX_X)})
cat(sprintf("COX %.17g %.17g %.17g\\n", c1$statistic, c1$parameter, c1$p.value))
r <- randtests::rank.test({_join(RANK_X)})
cat(sprintf("RANK %.17g %.17g %.17g\\n", r$statistic, r$P, r$p.value))
p <- nortest::pearson.test({_join(PEARSON_X)})
cat(sprintf("PEARSON %.17g %.17g %.17g %.17g\\n", p$statistic, p$df, p$p.value, p$n.classes))
"""


def _oracle():
    result = subprocess.run(
        ["Rscript", "-e", R_CODE],
        capture_output=True, text=True, check=True, timeout=180,
    )
    values = {}
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts:
            values[parts[0]] = [float(part) for part in parts[1:]]
    return values


def test_normality_and_trend_operators_match_r():
    oracle = _oracle()
    lillie = _run(LillieforsTestStep(), LILLIE_X)
    assert lillie.data[0, 0] == pytest.approx(oracle["LILLIE"][0], rel=1e-6)
    assert lillie.data[0, 1] == pytest.approx(oracle["LILLIE"][1], rel=1e-6)

    cox = _run(CoxStuartStep(), COX_X)
    assert cox.data[0, 0] == pytest.approx(oracle["COX"][0], abs=1e-6)
    assert cox.data[0, 1] == pytest.approx(oracle["COX"][1], abs=1e-6)
    assert cox.data[0, 2] == pytest.approx(oracle["COX"][2], rel=1e-6)

    rank = _run(RankTestStep(), RANK_X)
    assert rank.data[0, 0] == pytest.approx(oracle["RANK"][0], rel=1e-6)
    assert rank.data[0, 1] == pytest.approx(oracle["RANK"][1], abs=1e-6)
    assert rank.data[0, 4] == pytest.approx(oracle["RANK"][2], rel=1e-6)

    pearson = _run(PearsonTestStep(), PEARSON_X)
    assert pearson.data[0, 0] == pytest.approx(oracle["PEARSON"][0], rel=1e-6)
    assert pearson.data[0, 1] == pytest.approx(oracle["PEARSON"][1], abs=1e-6)
    assert pearson.data[0, 2] == pytest.approx(oracle["PEARSON"][2], rel=1e-6)
    assert pearson.data[0, 3] == pytest.approx(oracle["PEARSON"][3], abs=1e-6)
