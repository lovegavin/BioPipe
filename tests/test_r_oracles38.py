"""Authoritative R checks for the 0.54 regression diagnostics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.goldfeld_quandt import GoldfeldQuandtStep
from src.task.step.steps.rainbow_test import RainbowTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(x, y):
    n = len(x)
    data = np.column_stack((x, y))
    form = Form(
        np.asarray(data, dtype=np.float64),
        ["sample", "variable"],
        {
            "sample": {f"s{i}": i for i in range(n)},
            "variable": {"x": 0, "y": 1},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


R_SCRIPT = r"""
suppressPackageStartupMessages(library(lmtest))
x <- 1:20
y <- c(2,4,1,6,3,8,5,10,7,12,20,15,25,18,30,22,35,25,40,28)
g <- gqtest(y ~ x, order.by=x, data=data.frame(x=x, y=y))
cat(sprintf("GQ %.17g %.17g %.17g %.17g\n",
            as.numeric(g[["statistic"]]), as.numeric(g[["p.value"]]),
            as.numeric(g[["parameter"]][1]), as.numeric(g[["parameter"]][2])))
yr <- 1 + 0.5 * x + 4 * sin(pi * x / 10)
r <- raintest(yr ~ x, order.by=~x, data=data.frame(x=x, y=yr))
cat(sprintf("RA %.17g %.17g %.17g %.17g\n",
            as.numeric(r[["statistic"]]), as.numeric(r[["p.value"]]),
            as.numeric(r[["parameter"]][1]), as.numeric(r[["parameter"]][2])))
"""


def test_054_tests_match_r():
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    proc = subprocess.run([rscript, "-e", R_SCRIPT], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"GQ", "RA"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"GQ", "RA"}

    x = np.arange(1, 21, dtype=float)
    y = np.array(
        [2, 4, 1, 6, 3, 8, 5, 10, 7, 12, 20, 15, 25, 18, 30, 22, 35, 25, 40, 28],
        dtype=float,
    )
    _, out = _run(
        GoldfeldQuandtStep(),
        {"response": "y", "regressor": "x"},
        [_form(x, y)],
    )
    assert out.data[0, 0] == pytest.approx(values["GQ"][0], rel=1e-6)
    assert out.data[3, 0] == pytest.approx(values["GQ"][1], rel=1e-6)
    assert out.data[1, 0] == pytest.approx(values["GQ"][2])
    assert out.data[2, 0] == pytest.approx(values["GQ"][3])

    y_rain = 1.0 + 0.5 * x + 4.0 * np.sin(np.pi * x / 10.0)
    _, out = _run(
        RainbowTestStep(),
        {"response": "y", "regressor": "x"},
        [_form(x, y_rain)],
    )
    assert out.data[0, 0] == pytest.approx(values["RA"][0], rel=1e-6)
    assert out.data[3, 0] == pytest.approx(values["RA"][1], rel=1e-5)
    assert out.data[1, 0] == pytest.approx(values["RA"][2])
    assert out.data[2, 0] == pytest.approx(values["RA"][3])
