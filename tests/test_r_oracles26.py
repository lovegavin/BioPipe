"""Authoritative R checks for the 0.41 marginal-homogeneity and normality tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.bhapkar_test import BhapkarTestStep
from src.task.step.steps.shapiro_francia import ShapiroFranciaStep
from src.task.step.steps.von_neumann import VonNeumannStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _bhapkar():
    return _form(
        [[10, 5, 3], [4, 12, 6], [2, 4, 14]],
        ["row", "column"],
        {
            "row": {"low": 0, "mid": 1, "high": 2},
            "column": {"low": 0, "mid": 1, "high": 2},
        },
    )


def _series(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"x": 0},
        },
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
d <- commandArgs(TRUE)[1]
b <- as.matrix(read.csv(file.path(d, "bhapkar.csv"), header=FALSE))
r <- BhapkarTest(b)
cat(sprintf("B %.17g %.17g %.17g %.17g\n",
            r[["statistic"]][1,1], r[["parameter"]][1], r[["p.value"]][1,1], r[["N"]]))
x <- scan(file.path(d, "vn.csv"), quiet=TRUE)
v <- VonNeumannTest(x)
cat(sprintf("V %.17g %.17g %.17g\n",
            v[["statistic"]][["VN"]], v[["statistic"]][["z"]], v[["p.value"]]))
y <- scan(file.path(d, "sf.csv"), quiet=TRUE)
s <- ShapiroFranciaTest(y)
cat(sprintf("S %.17g %.17g\n", s[["statistic"]][["W"]], s[["p.value"]]))
"""


def test_041_operators_match_desc_tools(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    np.savetxt(tmp_path / "bhapkar.csv", np.array([[10, 5, 3], [4, 12, 6], [2, 4, 14]]), fmt="%d", delimiter=",")
    np.savetxt(tmp_path / "vn.csv", np.arange(1.0, 11.0), fmt="%.17g")
    np.savetxt(tmp_path / "sf.csv", np.array([
        2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
        18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
    ]), fmt="%.17g")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script), str(tmp_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)
    parsed = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts:
            parsed[parts[0]] = [float(v) for v in parts[1:]]

    bhapkar = _run(BhapkarTestStep(), {}, [_bhapkar()])
    assert bhapkar["statistic"] == pytest.approx(parsed["B"][0], rel=1e-10)
    assert bhapkar["df"] == parsed["B"][1]
    assert bhapkar["p"] == pytest.approx(parsed["B"][2], rel=1e-10)
    assert bhapkar["n"] == parsed["B"][3]

    vn = _run(VonNeumannStep(), {"value_label": "x"}, [_series(np.arange(1.0, 11.0))])
    assert vn["VN"] == pytest.approx(parsed["V"][0], rel=1e-10)
    assert vn["z"] == pytest.approx(parsed["V"][1], rel=1e-10)
    assert vn["p"] == pytest.approx(parsed["V"][2], rel=1e-10)

    sf = _run(ShapiroFranciaStep(), {"value_label": "x"}, [_series([
        2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
        18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
    ])])
    assert sf["W"] == pytest.approx(parsed["S"][0], rel=1e-7)
    assert sf["p"] == pytest.approx(parsed["S"][1], rel=1e-7)
