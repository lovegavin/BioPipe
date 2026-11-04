"""Authoritative R comparisons for 1.10.0 operators."""
from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.chisq_gof import ChisqGofStep
from src.task.step.steps.poisson_test import PoissonTestStep
from src.task.step.steps.proportion_ci import ProportionCiStep
from src.task.step.steps.rda import RdaStep

pytestmark = pytest.mark.skipif(
    shutil.which("Rscript") is None, reason="Rscript is not available")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float64), dims=dims, labels=labels,
                info={})
    form.validate()
    return form


def _table(names, columns, feature_names=None):
    feature_names = feature_names or list(columns)
    data = np.column_stack([columns[name] for name in feature_names])
    return _form(
        data,
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(names)},
         "feature": {name: j for j, name in enumerate(feature_names)}},
    )


def _run(step, inputs, params):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params["output"]]


def _run_r(code: str, cwd) -> list[float]:
    proc = subprocess.run(["Rscript", "-e", code], capture_output=True, text=True,
                          cwd=cwd, timeout=300)
    if proc.returncode == 2:
        pytest.skip("required R package is not available")
    assert proc.returncode == 0, proc.stderr
    return [float(value) for value in proc.stdout.split()]


def test_proportion_ci_matches_binom_and_prop_test():
    names = [f"x{i}" for i in range(4)]
    table = _table(names, {"successes": [30, 4, 0, 10], "trials": [100, 10, 5, 10]})
    exact = _run(ProportionCiStep(), (table,),
                 {"successes_label": "successes", "trials_label": "trials",
                  "method": "clopper_pearson", "output": "out"})
    wilson = _run(ProportionCiStep(), (table,),
                  {"successes_label": "successes", "trials_label": "trials",
                   "method": "wilson", "output": "out"})
    r_code = """
x <- c(30, 4, 0, 10); n <- c(100, 10, 5, 10)
cp <- t(sapply(seq_along(x), function(i) binom.test(x[i], n[i])$conf.int))
w <- t(sapply(seq_along(x), function(i) prop.test(x[i], n[i], correct=FALSE)$conf.int))
cat(sprintf("%.16g", c(cp, w)), sep="\\n")
"""
    # cat() flattens column-major: all lower bounds, then all upper bounds.
    values = np.asarray(_run_r(r_code, None))
    cp_ci = np.column_stack([values[0:4], values[4:8]])
    w_ci = np.column_stack([values[8:12], values[12:16]])
    exact_ci = exact.data[:, 1:3].astype(np.float64)
    wilson_ci = wilson.data[:, 1:3].astype(np.float64)
    assert np.allclose(exact_ci, cp_ci, atol=1e-6)
    assert np.allclose(wilson_ci, w_ci, atol=1e-6)


def test_poisson_test_matches_poisson_test():
    table = _table(["n1", "n2", "n3"],
                   {"counts": [5, 0, 12], "exposure": [1, 2, 4]})
    out = _run(PoissonTestStep(), (table,),
               {"counts_label": "counts", "exposure_label": "exposure",
                "rate": 2.0, "output": "out"})
    r_code = """
k <- c(5, 0, 12); tt <- c(1, 2, 4); r <- 2
res <- t(sapply(seq_along(k), function(i) {
  o <- poisson.test(k[i], T = tt[i], r = r)
  c(o$conf.int[1], o$conf.int[2], o$p.value)
}))
cat(sprintf("%.16g", res), sep="\\n")
"""
    # cat() flattens column-major: lower bounds, upper bounds, p-values.
    values = np.asarray(_run_r(r_code, None))
    ours = out.data.astype(np.float64)
    assert np.allclose(ours[:, 1], values[0:3], rtol=1e-5, atol=1e-7)
    assert np.allclose(ours[:, 2], values[3:6], rtol=1e-5, atol=1e-7)
    assert np.allclose(ours[:, 3], values[6:9], rtol=1e-5, atol=1e-7)


def test_chisq_gof_matches_chisq_test():
    table = _table(["a", "b", "c"], {"counts": [10, 20, 30]})
    out = _run(ChisqGofStep(), (table,),
               {"counts_label": "counts", "probabilities": [0.2, 0.3, 0.5],
                "output": "out"})
    r_code = """
ct <- chisq.test(c(10, 20, 30), p = c(0.2, 0.3, 0.5))
cat(sprintf("%.16g", c(unname(ct$statistic), ct$p.value)), sep="\\n")
"""
    statistic, p_value = _run_r(r_code, None)
    assert out.data[0, 0] == pytest.approx(statistic, rel=1e-5)
    assert out.data[2, 0] == pytest.approx(p_value, rel=1e-5, abs=1e-12)


def test_rda_matches_vegan_eigenvalues(tmp_path):
    rng = np.random.default_rng(20261102)
    x = rng.normal(size=(12, 2))
    y = x @ np.array([[1.0, 0.0, 0.5], [0.0, 1.0, -0.5]]) + 0.1 * rng.normal(size=(12, 3))
    names = [f"s{i}" for i in range(12)]
    response = _form(y, ["sample", "response"],
                     {"sample": {n: i for i, n in enumerate(names)},
                      "response": {"y1": 0, "y2": 1, "y3": 2}})
    explanatory = _form(x, ["sample", "predictor"],
                        {"sample": {n: i for i, n in enumerate(names)},
                         "predictor": {"x1": 0, "x2": 1}})
    out = _run(RdaStep(), (response, explanatory), {"n_axes": 4, "output": "out"})

    for data, header, filename in ((y, "y1", "y.csv"), (x, "x1", "x.csv")):
        with open(tmp_path / filename, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow([""] + (["y1", "y2", "y3"] if data is y else ["x1", "x2"]))
            for name, row in zip(names, data):
                writer.writerow([name] + [f"{value:.17g}" for value in row])

    r_code = """
if (!requireNamespace("vegan", quietly = TRUE)) quit(status = 2)
Y <- as.matrix(read.csv("y.csv", row.names = 1))
X <- as.data.frame(read.csv("x.csv", row.names = 1))
m <- vegan::rda(Y ~ ., data = X)
cat(sprintf("%.16g", as.numeric(m$CCA$eig)), sep="\\n")
"""
    values = np.asarray(_run_r(r_code, tmp_path))
    ours = out.data[:, 0].astype(np.float64)
    assert ours.size == values.size
    assert np.allclose(ours, values, rtol=1e-5, atol=1e-6)
