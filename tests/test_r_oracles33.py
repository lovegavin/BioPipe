"""Authoritative R checks for 0.49 block-rank and trend tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.cuzick_test import CuzickTestStep
from src.task.step.steps.durbin_test import DurbinTestStep
from src.task.step.steps.skillings_mack import SkillingsMackTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _durbin():
    return _form(
        np.array(
            [
                [1, 2, 3, np.nan],
                [4, 5, np.nan, 6],
                [7, np.nan, 8, 9],
                [np.nan, 10, 11, 12],
            ],
            dtype=float,
        ),
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(4)},
            "treatment": {f"T{i}": i for i in range(4)},
        },
    )


def _skillings():
    return _form(
        np.array(
            [
                [1, 2, 3, np.nan],
                [2, 3, np.nan, 4],
                [3, np.nan, 4, 5],
                [np.nan, 4, 5, 6],
                [5, 6, np.nan, 7],
            ],
            dtype=float,
        ),
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(5)},
            "treatment": {f"T{i}": i for i in range(4)},
        },
    )


def _grouped():
    values = np.array([1, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13], dtype=float)
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(18)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(18)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


R_SCRIPT = r"""
suppressPackageStartupMessages(library(PMCMRplus))
m <- matrix(c(1,2,3,NA, 4,5,NA,6, 7,NA,8,9, NA,10,11,12), nrow=4, byrow=TRUE)
d <- durbinTest(m)
cat(sprintf("DUR %.17g %.17g %.17g\n",
            as.numeric(unname(d[["statistic"]])),
            as.numeric(unname(d[["parameter"]])),
            as.numeric(unname(d[["p.value"]]))))
s <- matrix(c(1,2,3,NA, 2,3,NA,4, 3,NA,4,5, NA,4,5,6, 5,6,NA,7), nrow=5, byrow=TRUE)
sm <- skillingsMackTest(s)
cat(sprintf("SKM %.17g %.17g %.17g\n",
            as.numeric(unname(sm[["statistic"]])),
            as.numeric(unname(sm[["parameter"]])),
            as.numeric(sm[["p.value"]][1,1])))
x <- c(1,2,3,4,5,6, 4,5,6,7,8,9, 8,9,10,11,12,13)
g <- factor(rep(c("A","B","C"), each=6))
cz <- cuzickTest(x, g)
cat(sprintf("CUZ %.17g %.17g %.17g\n",
            as.numeric(unname(cz[["statistic"]])),
            as.numeric(unname(cz[["p.value"]])),
            as.numeric(unname(cz[["estimate"]]))))
"""


def test_049_operators_match_r(tmp_path):
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
        if parts and parts[0] in {"DUR", "SKM", "CUZ"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"DUR", "SKM", "CUZ"}

    result, _ = _run(DurbinTestStep(), {}, [_durbin()])
    assert result["statistic"] == pytest.approx(values["DUR"][0], rel=1e-6)
    assert result["df"] == int(values["DUR"][1])
    assert result["p"] == pytest.approx(values["DUR"][2], rel=1e-6)

    result, _ = _run(SkillingsMackTestStep(), {}, [_skillings()])
    assert result["statistic"] == pytest.approx(values["SKM"][0], rel=1e-6)
    assert result["df"] == int(values["SKM"][1])
    assert result["p"] == pytest.approx(values["SKM"][2], rel=1e-6)

    expression, meta = _grouped()
    _, out = _run(CuzickTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data[0, 0] == pytest.approx(values["CUZ"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["CUZ"][1], rel=1e-6)
    assert out.data[0, 2] == pytest.approx(values["CUZ"][2], rel=1e-6)
