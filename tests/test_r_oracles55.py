"""R oracle checks for 0.71 Zivot-Andrews and exact Poisson rate tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.poisson_means_test import PoissonMeansTestStep
from src.task.step.steps.zivot_andrews import ZivotAndrewsStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_r_oracles_for_071(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    rng = np.random.default_rng(20261101)
    values = np.cumsum(rng.normal(size=80)) + np.r_[np.zeros(40), np.full(40, 3.0)]
    np.savetxt(tmp_path / "za.csv", values, delimiter=",")
    counts = np.asarray([[10], [20], [30], [40], [5], [10], [15], [20]], dtype=float)
    groups = np.asarray([[0]] * 4 + [[1]] * 4, dtype=float)
    np.savetxt(tmp_path / "counts.csv", counts, delimiter=",")
    np.savetxt(tmp_path / "groups.csv", groups, delimiter=",")
    script = r"""
suppressPackageStartupMessages(library(urca))
x <- scan(file.path(commandArgs(TRUE)[1], "za.csv"), quiet=TRUE)
z <- ur.za(x, model="intercept", lag=2)
cat("ZA", sprintf("%.17g", c(z@teststat, z@bpoint)), "\n")
k <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "counts.csv"), header=FALSE))
g <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "groups.csv"), header=FALSE))
k1 <- sum(k[g == 0, 1]); k2 <- sum(k[g == 1, 1])
n1 <- sum(g == 0); n2 <- sum(g == 1)
p <- poisson.test(c(k1, k2), T=c(n1, n2))
cat("POIS", sprintf("%.17g", c(p$p.value, p$estimate, p$conf.int[1], p$conf.int[2])), "\n")
"""
    proc = subprocess.run(["Rscript", "-e", script, str(tmp_path)], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R urca not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values_out = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"ZA", "POIS"}:
            values_out[parts[0]] = [float(v) for v in parts[1:]]
    assert set(values_out) == {"ZA", "POIS"}

    za = _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(80)}, "feature": {"x": 0}},
    )
    za_result, _ = _run(ZivotAndrewsStep(), {"value_label": "x", "regression": "c", "lags": 2}, [za])
    assert za_result["statistic"] == pytest.approx(values_out["ZA"][0], abs=1e-6)
    assert za_result["break_index"] + 1 == values_out["ZA"][1]

    expr = _form(
        counts,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"counts": 0}},
    )
    meta = _form(
        groups,
        ["sample", "group"],
        {"sample": {f"s{i}": i for i in range(8)}, "group": {"g": 0}},
    )
    _result, out = _run(
        PoissonMeansTestStep(),
        {"group_label": "g", "group_a": "0", "group_b": "1"},
        [expr, meta],
    )
    row = out.data[0]
    assert row[7] == pytest.approx(values_out["POIS"][0], rel=1e-9)
    assert row[6] == pytest.approx(values_out["POIS"][1], rel=1e-9)
    assert row[8] == pytest.approx(values_out["POIS"][2], rel=1e-9)
    assert row[9] == pytest.approx(values_out["POIS"][3], rel=1e-9)
