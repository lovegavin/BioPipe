"""Authoritative R checks for the 0.20 distance and regression operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.anosim import AnosimStep
from src.task.step.steps.egger_test import EggerTestStep
from src.task.step.steps.partial_mantel import PartialMantelStep
from src.task.step.steps.procrustes import ProcrustesStep


R_SCRIPT = r"""
suppressPackageStartupMessages(library(vegan))
D <- matrix(c(0,1,2,7,8,9, 1,0,3,6,7,8, 2,3,0,5,6,7, 7,6,5,0,1,2, 8,7,6,1,0,3, 9,8,7,2,3,0), nrow=6, byrow=TRUE)
a <- anosim(as.dist(D), c(0,0,0,1,1,1), permutations=0)
cat("ANOSIM", a$statistic, "\n")
X <- matrix(c(1,2, 2,1, 3,4, 4,3, 5,6), nrow=5, byrow=TRUE)
Y <- X %*% matrix(c(0.8,0.6,-0.6,0.8), nrow=2) + matrix(c(2,-1), nrow=5, ncol=2, byrow=TRUE)
p <- procrustes(X, Y, scale=TRUE, symmetric=FALSE)
cat("PROC", p$ss, p$scale, "\n")
eff <- c(0.2,-0.1,0.4,0.3,0.05,0.5)
se <- c(0.05,0.08,0.1,0.12,0.07,0.2)
m <- lm(I(eff/se) ~ I(1/se))
cat("EGGER", unlist(summary(m)$coefficients), "\n")
B <- matrix(c(0,2,3,6,7,8, 2,0,4,5,6,7, 3,4,0,4,5,6, 6,5,4,0,2,3, 7,6,5,2,0,4, 8,7,6,3,4,0), nrow=6, byrow=TRUE)
C <- matrix(c(0,1,1,5,5,6, 1,0,2,5,5,6, 1,2,0,4,5,6, 5,5,4,0,1,1, 5,5,5,1,0,2, 6,6,6,1,2,0), nrow=6, byrow=TRUE)
pm <- mantel.partial(as.dist(D), as.dist(B), as.dist(C), permutations=0)
cat("PARTIAL", pm$statistic, "\n")
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _distance(matrix):
    names = [f"s{i}" for i in range(matrix.shape[0])]
    return _form(matrix, ["sample", "sample_b"],
                 {"sample": _labels(names), "sample_b": _labels(names)})


def _r_values():
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    result = subprocess.run(
        ["Rscript", "-e", R_SCRIPT], capture_output=True, text=True, timeout=120
    )
    if result.returncode != 0:
        pytest.skip(f"R oracle failed: {result.stderr[-500:]}")
    values = {}
    for line in result.stdout.splitlines():
        fields = line.split()
        if fields:
            values[fields[0]] = [float(value) for value in fields[1:]]
    return values


def test_r_oracles_for_anosim_procrustes_egger_and_partial_mantel():
    r = _r_values()
    d = np.array([[0, 1, 2, 7, 8, 9], [1, 0, 3, 6, 7, 8], [2, 3, 0, 5, 6, 7],
                  [7, 6, 5, 0, 1, 2], [8, 7, 6, 1, 0, 3], [9, 8, 7, 2, 3, 0]], dtype=np.float32)
    meta = _form(np.array([[0], [0], [0], [1], [1], [1]]), ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]), "feature": {"group": 0}})
    _, anosim = _run(AnosimStep(), {"group_label": "group", "n_perm": 99}, [_distance(d), meta])
    assert anosim["R"] == pytest.approx(r["ANOSIM"][0], abs=1e-7)

    x = np.array([[1, 2], [2, 1], [3, 4], [4, 3], [5, 6]], dtype=np.float32)
    rotation = np.array([[0.8, -0.6], [0.6, 0.8]])
    y = x @ rotation + np.array([2, -1])
    fx = _form(x, ["sample", "axis"], {"sample": _labels([f"s{i}" for i in range(5)]),
                                       "axis": _labels(["a0", "a1"])})
    fy = _form(y, ["sample", "axis"], {"sample": _labels([f"s{i}" for i in range(5)]),
                                       "axis": _labels(["a0", "a1"])})
    _, proc = _run(ProcrustesStep(), {}, [fx, fy])
    assert proc["ss"] == pytest.approx(r["PROC"][0], abs=1e-8)
    expected_r = np.sqrt(max(0.0, 1.0 - r["PROC"][0] / np.sum(x * x)))
    assert proc["r"] == pytest.approx(expected_r, rel=1e-6)
    assert proc["scale"] == pytest.approx(r["PROC"][1], rel=1e-6)

    effect = np.array([0.2, -0.1, 0.4, 0.3, 0.05, 0.5], dtype=np.float32)
    se = np.array([0.05, 0.08, 0.1, 0.12, 0.07, 0.2], dtype=np.float32)
    table = _form(np.column_stack([effect, se]), ["study", "statistic"],
                  {"study": _labels([f"s{i}" for i in range(6)]),
                   "statistic": _labels(["effect", "se"])})
    _, egger = _run(EggerTestStep(), {}, [table])
    assert egger["intercept"] == pytest.approx(r["EGGER"][0], rel=1e-5)
    assert egger["slope"] == pytest.approx(r["EGGER"][1], rel=1e-5)
    assert egger["p_intercept"] == pytest.approx(r["EGGER"][6], rel=1e-5)

    b = np.array([[0, 2, 3, 6, 7, 8], [2, 0, 4, 5, 6, 7], [3, 4, 0, 4, 5, 6],
                  [6, 5, 4, 0, 2, 3], [7, 6, 5, 2, 0, 4], [8, 7, 6, 3, 4, 0]], dtype=np.float32)
    c = np.array([[0, 1, 1, 5, 5, 6], [1, 0, 2, 5, 5, 6], [1, 2, 0, 4, 5, 6],
                  [5, 5, 4, 0, 1, 1], [5, 5, 5, 1, 0, 2], [6, 6, 6, 1, 2, 0]], dtype=np.float32)
    _, partial = _run(PartialMantelStep(), {"n_perm": 99}, [_distance(d), _distance(b), _distance(c)])
    assert partial["r"] == pytest.approx(r["PARTIAL"][0], rel=1e-5)
