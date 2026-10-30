"""Authoritative R checks for 0.60 time-series, Stuart-Maxwell, and VI."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.box_pierce import BoxPierceStep
from src.task.step.steps.stuart_maxwell_test import StuartMaxwellTestStep
from src.task.step.steps.variation_of_information import VariationOfInformationStep


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
    return step.export(ctx), ctx[params.get("output", step.name)]


def _series(values):
    values = np.asarray(values, dtype=float)
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {"value": 0}},
    )


def _table(rows):
    rows = np.asarray(rows, dtype=float)
    return _form(
        rows,
        ["row", "column"],
        {
            "row": {f"r{i}": i for i in range(rows.shape[0])},
            "column": {f"c{i}": i for i in range(rows.shape[1])},
        },
    )


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    return _form(
        values,
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
suppressPackageStartupMessages(library(aricode))
options(digits=17)
x <- c(1,2,3,4,5,4,3,2,1,2,3,4)
bp <- Box.test(x, lag=3, type="Box-Pierce")
cat(sprintf("BP %.17g %.17g %.17g\n", unname(bp[["statistic"]]), bp[["parameter"]], bp[["p.value"]]))
m <- matrix(c(20,10,5, 8,25,7, 6,9,30), nrow=3, byrow=TRUE)
sm <- StuartMaxwellTest(m)
cat(sprintf("SM %.17g %.17g %.17g %.17g\n", unname(sm[["statistic"]]), sm[["parameter"]], sm[["p.value"]], sm[["N"]]))
a <- c(1,1,1,2,2,2,3,3,3)
b <- c(1,1,2,2,3,3,1,2,3)
cat(sprintf("NVI %.17g\n", aricode::NVI(a,b)))
"""


def test_060_operators_match_r(tmp_path):
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
    rows = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts:
            rows[parts[0]] = [float(value) for value in parts[1:]]
    assert set(rows) == {"BP", "SM", "NVI"}

    _, out = _run(
        BoxPierceStep(),
        {"value_label": "value", "lags": 3},
        [_series([1, 2, 3, 4, 5, 4, 3, 2, 1, 2, 3, 4])],
    )
    assert out.data[0, 0] == pytest.approx(rows["BP"][0], rel=1e-8)
    assert out.data[2, 0] == pytest.approx(rows["BP"][2], rel=1e-8)

    _, out = _run(StuartMaxwellTestStep(), {}, [_table([[20, 10, 5], [8, 25, 7], [6, 9, 30]])])
    assert out.data[0, 0] == pytest.approx(rows["SM"][0], rel=1e-8)
    assert out.data[2, 0] == pytest.approx(rows["SM"][2], rel=1e-8)

    _, out = _run(
        VariationOfInformationStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [_labels([1, 1, 1, 2, 2, 2, 3, 3, 3]), _labels([1, 1, 2, 2, 3, 3, 1, 2, 3])],
    )
    assert out.data[1, 0] == pytest.approx(rows["NVI"][0], rel=1e-8)
