"""Authoritative R checks for the 0.42 normality and extreme-reaction tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.lillie_test import LillieTestStep
from src.task.step.steps.moses_test import MosesTestStep
from src.task.step.steps.shapiro_wilk import ShapiroWilkStep


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


def _moses_frame():
    values = np.array([10, 12, 14, 15, 16, 18, 20, 22, 24, 26, 1, 2, 3, 4, 5, 6, 7, 8, 9, 11], dtype=float)
    groups = np.r_[np.zeros(10), np.ones(10)]
    return _form(
        np.column_stack([values, groups]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(20)},
            "feature": {"value": 0, "g": 1},
        },
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
d <- commandArgs(TRUE)[1]
y <- scan(file.path(d, "normality.csv"), quiet=TRUE)
s <- shapiro.test(y)
cat(sprintf("W %.17g %.17g\n", s[["statistic"]][["W"]], s[["p.value"]]))
l <- LillieTest(y)
cat(sprintf("L %.17g %.17g\n", l[["statistic"]][["D"]], l[["p.value"]]))
x <- scan(file.path(d, "moses_x.csv"), quiet=TRUE)
z <- scan(file.path(d, "moses_y.csv"), quiet=TRUE)
m <- MosesTest(x, z)
cat(sprintf("M %.17g %.17g\n", m[["statistic"]][["S"]], m[["p.value"]]))
"""


def test_042_operators_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    values = np.array([
        2.1, 3.9, 5.2, 7.1, 8.8, 10.2, 12.0, 13.8, 15.1, 17.2,
        18.8, 20.1, 22.0, 23.9, 25.2, 27.1, 28.8, 30.2, 32.0, 33.8,
    ])
    np.savetxt(tmp_path / "normality.csv", values, fmt="%.17g")
    np.savetxt(tmp_path / "moses_x.csv", np.array([10, 12, 14, 15, 16, 18, 20, 22, 24, 26]), fmt="%d")
    np.savetxt(tmp_path / "moses_y.csv", np.array([1, 2, 3, 4, 5, 6, 7, 8, 9, 11]), fmt="%d")
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

    sw = _run(ShapiroWilkStep(), {"value_label": "x"}, [_series(values)])
    assert sw["W"] == pytest.approx(parsed["W"][0], rel=1e-9)
    assert sw["p"] == pytest.approx(parsed["W"][1], rel=1e-7)

    lillie = _run(LillieTestStep(), {"value_label": "x"}, [_series(values)])
    assert lillie["D"] == pytest.approx(parsed["L"][0], rel=1e-12)
    assert lillie["p"] == pytest.approx(parsed["L"][1], rel=1e-12)

    moses = _run(MosesTestStep(), {
        "value_label": "value", "group_label": "g", "group_a": "0", "group_b": "1",
    }, [_moses_frame()])
    assert moses["S"] == parsed["M"][0]
    assert moses["p"] == pytest.approx(parsed["M"][1], rel=1e-12)
