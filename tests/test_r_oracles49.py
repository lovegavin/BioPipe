"""Authoritative R checks for 0.65 variance ratio and Krippendorff's alpha."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.krippendorff_alpha import KrippendorffAlphaStep
from src.task.step.steps.variance_ratio import VarianceRatioStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _series(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    form = Form(
        data,
        ["sample", "value"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "value": {"value": 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _matrix(values):
    data = np.asarray(values, dtype=np.float64)
    form = Form(
        data,
        ["subject", "rater"],
        {
            "subject": {f"s{i}": i for i in range(data.shape[0])},
            "rater": {f"r{i}": i for i in range(data.shape[1])},
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
library(irr)
v <- var.test(1:5, c(2, 4, 6, 8, 10))
cat(sprintf("%.17g\n", v[["statistic"]][[1]]))
cat(sprintf("%.17g\n", v[["parameter"]][[1]]))
cat(sprintf("%.17g\n", v[["parameter"]][[2]]))
cat(sprintf("%.17g\n", v[["p.value"]]))
cat(sprintf("%.17g\n", v[["conf.int"]][1]))
cat(sprintf("%.17g\n", v[["conf.int"]][2]))
m <- matrix(c(1, 2, 3, 4,
              1, 2, 3, 4,
              2, 2, 4, 4,
              NA, 3, 3, 4), nrow = 4, byrow = TRUE)
cat(sprintf("%.17g\n", irr::kripp.alpha(t(m), method = "nominal")[["value"]]))
cat(sprintf("%.17g\n", irr::kripp.alpha(t(m), method = "interval")[["value"]]))
"""


def test_065_variance_and_krippendorff_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    values = [float(line) for line in proc.stdout.strip().splitlines()]

    _, variance = _run(VarianceRatioStep(), {}, [_series([1, 2, 3, 4, 5]), _series([2, 4, 6, 8, 10])])
    assert variance.data[0, 0] == pytest.approx(values[0], rel=1e-12)
    assert variance.data[0, 1] == pytest.approx(values[1], rel=1e-12)
    assert variance.data[0, 2] == pytest.approx(values[2], rel=1e-12)
    assert variance.data[0, 3] == pytest.approx(values[3], rel=1e-12)
    assert variance.data[0, 4] == pytest.approx(values[4], rel=1e-12)
    assert variance.data[0, 5] == pytest.approx(values[5], rel=1e-12)

    missing = [[1, 2, 3, 4], [1, 2, 3, 4], [2, 2, 4, 4], [np.nan, 3, 3, 4]]
    _, nominal = _run(KrippendorffAlphaStep(), {"level": "nominal"}, [_matrix(missing)])
    _, interval = _run(KrippendorffAlphaStep(), {"level": "interval"}, [_matrix(missing)])
    assert nominal.data[0, 0] == pytest.approx(values[6], rel=1e-12)
    assert interval.data[0, 0] == pytest.approx(values[7], rel=1e-12)
