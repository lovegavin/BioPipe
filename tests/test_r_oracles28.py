"""Authoritative R checks for the 0.43 block/randomness tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.mardia_test import MardiaTestStep
from src.task.step.steps.page_test import PageTestStep
from src.task.step.steps.turning_point_test import TurningPointTestStep


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


def _page_matrix():
    return _form(
        np.array([
            [1, 2, 3, 4],
            [2, 1, 3, 4],
            [1, 3, 2, 4],
            [2, 3, 1, 4],
            [1, 2, 4, 3],
            [2, 1, 3, 4],
            [1, 3, 2, 4],
            [1, 2, 3, 4],
        ], dtype=float),
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(8)},
            "treatment": {f"t{j}": j for j in range(4)},
        },
    )


def _mardia_matrix():
    idx = np.arange(1.0, 61.0)
    return _form(
        np.column_stack([idx, np.sin(idx), np.cos(idx / 3.0)]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(60)},
            "feature": {"x1": 0, "x2": 1, "x3": 2},
        },
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
suppressPackageStartupMessages(library(randtests))
suppressPackageStartupMessages(library(psych))
d <- commandArgs(TRUE)[1]
page <- as.matrix(read.csv(file.path(d, "page.csv"), header=FALSE))
pt <- PageTest(page)
cat(sprintf("PAGE L %.17g p %.17g\n", pt[["statistic"]][["L"]], pt[["p.value"]]))
m <- as.matrix(read.csv(file.path(d, "mardia.csv"), header=FALSE))
md <- psych::mardia(m, plot=FALSE)
for (k in c("b1p", "b2p", "skew", "small.skew", "p.skew", "p.small", "kurtosis", "p.kurt")) {
  cat(sprintf("MARDIA %s %.17g\n", k, md[[k]]))
}
y <- scan(file.path(d, "turning.csv"), quiet=TRUE)
tp <- turning.point.test(y)
cat(sprintf("TP z %.17g p %.17g turns %.17g\n", tp[["statistic"]][["statistic"]], tp[["p.value"]], tp[["tp"]]))
"""


def test_043_operators_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    page = np.array([
        [1, 2, 3, 4],
        [2, 1, 3, 4],
        [1, 3, 2, 4],
        [2, 3, 1, 4],
        [1, 2, 4, 3],
        [2, 1, 3, 4],
        [1, 3, 2, 4],
        [1, 2, 3, 4],
    ], dtype=float)
    np.savetxt(tmp_path / "page.csv", page, delimiter=",", fmt="%.17g")
    idx = np.arange(1.0, 61.0)
    mardia = np.column_stack([idx, np.sin(idx), np.cos(idx / 3.0)])
    np.savetxt(tmp_path / "mardia.csv", mardia, delimiter=",", fmt="%.17g")
    np.savetxt(tmp_path / "turning.csv", np.array([1, 3, 2, 5, 4, 7, 6, 9, 8, 10]), fmt="%d")
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
            expected.setdefault(tag, {})
            for i in range(1, len(parts), 2):
                expected[tag][parts[i]] = float(parts[i + 1])

    page_result = _run(PageTestStep(), {}, [_page_matrix()])
    assert page_result["L"] == expected["PAGE"]["L"]
    assert page_result["p"] == pytest.approx(expected["PAGE"]["p"], rel=1e-10)

    mardia_result = _run(MardiaTestStep(), {}, [_mardia_matrix()])
    r_keys = {
        "b1p": "b1p", "b2p": "b2p", "skew": "skew", "small_skew": "small.skew",
        "p_skew": "p.skew", "p_small": "p.small", "kurtosis": "kurtosis", "p_kurt": "p.kurt",
    }
    for key, r_key in r_keys.items():
        assert mardia_result[key] == pytest.approx(expected["MARDIA"][r_key], rel=1e-10)

    turning_result = _run(
        TurningPointTestStep(), {"value_label": "x"},
        [_series([1, 3, 2, 5, 4, 7, 6, 9, 8, 10])],
    )
    assert turning_result["z"] == pytest.approx(expected["TP"]["z"], rel=1e-10)
    assert turning_result["p"] == pytest.approx(expected["TP"]["p"], rel=1e-10)
    assert turning_result["turns"] == expected["TP"]["turns"]
