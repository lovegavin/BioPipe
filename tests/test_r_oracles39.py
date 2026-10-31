"""Authoritative R checks for 0.55 kurtosis and sphericity tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.anscombe_glynn import AnscombeGlynnStep
from src.task.step.steps.bonett_seier import BonettSeierStep
from src.task.step.steps.mauchly_test import MauchlyTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"value": 0}},
    )


def _matrix(values):
    n, p = values.shape
    return _form(
        values,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(n)},
            "feature": {f"f{j}": j for j in range(p)},
        },
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(moments))
x <- c(1,2,3,4,5,6,8,10,12,14,16,20)
a <- anscombe.test(x)
cat(sprintf("AG %.17g %.17g %.17g\n",
            as.numeric(a[["statistic"]][["kurt"]]),
            as.numeric(a[["statistic"]][["z"]]),
            as.numeric(a[["p.value"]])))
b <- bonett.test(x)
cat(sprintf("BO %.17g %.17g %.17g\n",
            as.numeric(b[["statistic"]][["tau"]]),
            as.numeric(b[["statistic"]][["z"]]),
            as.numeric(b[["p.value"]])))
Y <- matrix(c(1,2,3, 2,4,5, 3,5,7, 4,8,8, 5,9,10, 6,11,13),
            ncol=3, byrow=TRUE)
SSD <- crossprod(sweep(Y, 2, colMeans(Y)))
obj <- list(SSD=SSD, df=nrow(Y)-1, call=quote(Y))
m <- stats:::mauchly.test.SSD(obj, T=diag(3))
cat(sprintf("MA %.17g %.17g\n",
            as.numeric(m[["statistic"]][["W"]]),
            as.numeric(m[["p.value"]])))
"""


def test_055_tests_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"AG", "BO", "MA"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"AG", "BO", "MA"}

    values_x = [1, 2, 3, 4, 5, 6, 8, 10, 12, 14, 16, 20]
    _, out = _run(AnscombeGlynnStep(), {"value_label": "value"}, [_series(values_x)])
    assert out.data[0, 0] == pytest.approx(values["AG"][0], rel=1e-9)
    assert out.data[1, 0] == pytest.approx(values["AG"][1], rel=1e-9)
    assert out.data[2, 0] == pytest.approx(values["AG"][2], rel=1e-9)

    _, out = _run(BonettSeierStep(), {"value_label": "value"}, [_series(values_x)])
    assert out.data[0, 0] == pytest.approx(values["BO"][0], rel=1e-9)
    assert out.data[1, 0] == pytest.approx(values["BO"][1], rel=1e-9)
    assert out.data[2, 0] == pytest.approx(values["BO"][2], rel=1e-9)

    y = np.array(
        [
            [1.0, 2.0, 3.0],
            [2.0, 4.0, 5.0],
            [3.0, 5.0, 7.0],
            [4.0, 8.0, 8.0],
            [5.0, 9.0, 10.0],
            [6.0, 11.0, 13.0],
        ]
    )
    _, out = _run(MauchlyTestStep(), {}, [_matrix(y)])
    assert out.data[0, 0] == pytest.approx(values["MA"][0], rel=1e-9)
    assert out.data[3, 0] == pytest.approx(values["MA"][1], rel=1e-9)
