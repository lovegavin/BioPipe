"""Authoritative R checks for the 0.44 trend/outlier/normality tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.anderson_darling import AndersonDarlingStep
from src.task.step.steps.cox_stuart_test import CoxStuartTestStep
from src.task.step.steps.grubbs_test import GrubbsTestStep


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
suppressPackageStartupMessages(library(outliers))
suppressPackageStartupMessages(library(nortest))
suppressPackageStartupMessages(library(randtests))
d <- commandArgs(TRUE)[1]
cx <- scan(file.path(d, "cox.csv"), quiet=TRUE)
cs <- cox.stuart.test(cx)
cat(sprintf("COX t %.17g n %.17g p %.17g\n",
            cs[["statistic"]][["statistic"]], cs[["parameter"]][["n"]], cs[["p.value"]]))
gx <- scan(file.path(d, "grubbs.csv"), quiet=TRUE)
g <- grubbs.test(gx)
cat(sprintf("GRUBBS G %.17g U %.17g p %.17g\n",
            g[["statistic"]][["G"]], g[["statistic"]][["U"]], g[["p.value"]]))
ax <- scan(file.path(d, "ad.csv"), quiet=TRUE)
a <- ad.test(ax)
cat(sprintf("AD A %.17g p %.17g n %.17g\n",
            a[["statistic"]][["A"]], a[["p.value"]], length(ax)))
"""


def test_044_operators_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    trend = [1, 2, 4, 3, 5, 7, 6, 8, 9, 11, 10, 12, 14, 13, 15, 17, 16, 18, 19, 21]
    grubbs = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 25]
    np.savetxt(tmp_path / "cox.csv", np.asarray(trend), fmt="%.17g")
    np.savetxt(tmp_path / "grubbs.csv", np.asarray(grubbs), fmt="%.17g")
    np.savetxt(tmp_path / "ad.csv", np.asarray(trend), fmt="%.17g")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script), str(tmp_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)

    expected = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3 and len(parts) % 2 == 1:
            tag = parts[0]
            expected[tag] = {parts[i]: float(parts[i + 1]) for i in range(1, len(parts), 2)}

    cox = _run(CoxStuartTestStep(), {"value_label": "x"}, [_series(trend)])
    assert cox["t"] == expected["COX"]["t"]
    assert cox["n"] == expected["COX"]["n"]
    assert cox["p"] == pytest.approx(expected["COX"]["p"], rel=1e-10)

    gr = _run(GrubbsTestStep(), {"value_label": "x"}, [_series(grubbs)])
    assert gr["G"] == pytest.approx(expected["GRUBBS"]["G"], rel=1e-10)
    assert gr["U"] == pytest.approx(expected["GRUBBS"]["U"], rel=1e-10)
    assert gr["p"] == pytest.approx(expected["GRUBBS"]["p"], rel=1e-10)

    ad = _run(AndersonDarlingStep(), {"value_label": "x"}, [_series(trend)])
    assert ad["A"] == pytest.approx(expected["AD"]["A"], rel=1e-10)
    assert ad["p"] == pytest.approx(expected["AD"]["p"], rel=1e-10)
    assert ad["n"] == expected["AD"]["n"]
