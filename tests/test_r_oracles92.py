"""R oracle checks for the 1.11.0 statistics and species-pool operators."""
from __future__ import annotations

import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.periodogram import PeriodogramStep
from src.task.step.steps.specpool import SpecpoolStep
from src.task.step.steps.turning_point import TurningPointStep
from src.task.step.steps.weighted_kappa import WeightedKappaStep

R_CODE = r"""
suppressMessages(library(irr))
suppressMessages(library(randtests))
suppressMessages(library(vegan))
r1 <- c(1,2,3,1,2,3,1,2,3,1,2,3,1,2,3,1,2,3)
r2 <- c(1,2,2,1,3,3,1,2,2,1,3,3,1,2,2,1,3,2)
k <- irr::kappa2(cbind(r1, r2), weight = "equal")
cat("kappa", sprintf("%.17g", c(k[["value"]], k[["statistic"]], k[["p.value"]])), "\n")
x <- c(1,3,2,4,3,5,4,6,5,7,6,9,7,8,10,9,11,10)
t <- randtests::turning.point.test(x)
cat("turning", sprintf("%.17g", c(t[["statistic"]], t[["tp"]], t[["p.value"]], t[["n"]])), "\n")
y <- c(1,2,1,2,1,2,1,2,9,1,2,1)
sp <- stats::spec.pgram(y, taper=0, spans=NULL, detrend=FALSE, demean=TRUE, pad=0, fast=FALSE, plot=FALSE)
cat("spec", sprintf("%.17g", c(sp[["freq"]], sp[["spec"]])), "\n")
comm <- rbind(c(10,5,1,0,0), c(8,4,2,1,0), c(12,6,0,0,0), c(0,3,7,2,1), c(0,1,5,3,2), c(1,0,2,6,4))
sp2 <- vegan::specpool(comm, pool=c("A","A","A","B","B","B"), smallsample=TRUE)
cat("pool", sprintf("%.17g", as.matrix(sp2)), "\n")
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _labels(names):
    return {name: index for index, name in enumerate(names)}


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float32), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)]


def _series_form(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    return _form(data, ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(data.shape[0])]),
                  "feature": {"value": 0}})


RATING_1 = np.array([1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3, 1, 2, 3])
RATING_2 = np.array([1, 2, 2, 1, 3, 3, 1, 2, 2, 1, 3, 3, 1, 2, 2, 1, 3, 2])
TURNING = np.array([1, 3, 2, 4, 3, 5, 4, 6, 5, 7, 6, 9, 7, 8, 10, 9, 11, 10])
PERIOD = np.array([1, 2, 1, 2, 1, 2, 1, 2, 9, 1, 2, 1])
COMM = np.array([[10, 5, 1, 0, 0], [8, 4, 2, 1, 0], [12, 6, 0, 0, 0],
                 [0, 3, 7, 2, 1], [0, 1, 5, 3, 2], [1, 0, 2, 6, 4]], dtype=np.float64)


@pytest.mark.skipif(
    subprocess.run(["bash", "-lc", "command -v Rscript"],
                   capture_output=True).returncode != 0,
    reason="Rscript is unavailable",
)
def test_statistics_and_specpool_oracles():
    proc = subprocess.run(["Rscript", "-e", R_CODE], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"kappa", "turning", "spec", "pool"}:
            values[parts[0]] = np.array([float(item) for item in parts[1:]])

    kappa = _run(WeightedKappaStep(), {"weights": "linear"},
                 (_form(np.column_stack([RATING_1, RATING_2]), ["subject", "rater"],
                        {"subject": _labels([f"s{i}" for i in range(18)]),
                         "rater": {"a": 0, "b": 1}}),))
    assert kappa.data[0, 0] == pytest.approx(values["kappa"][0], rel=1e-6)
    assert kappa.data[2, 0] == pytest.approx(values["kappa"][1], rel=1e-5)
    assert kappa.data[3, 0] == pytest.approx(values["kappa"][2], rel=1e-4)

    turning = _run(TurningPointStep(), {"value_label": "value"},
                   (_series_form(TURNING),))
    assert turning.data[0, 0] == pytest.approx(values["turning"][0], rel=1e-6)
    assert turning.data[0, 1] == values["turning"][1]
    assert turning.data[0, 2] == pytest.approx(values["turning"][2], rel=1e-4)
    assert turning.data[0, 3] == values["turning"][3]

    spectrum = _run(PeriodogramStep(), {"value_label": "value"},
                    (_series_form(PERIOD),))
    expected = values["spec"]
    assert spectrum.data[:, 0] == pytest.approx(expected[:6], rel=1e-6)
    assert spectrum.data[:, 1] == pytest.approx(expected[6:], rel=1e-6)

    meta = _form(np.array([[0], [0], [0], [1], [1], [1]], dtype=np.float64),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]),
                  "feature": {"pool": 0}})
    abundance = _form(COMM, ["sample", "taxon"],
                      {"sample": _labels([f"s{i}" for i in range(6)]),
                       "taxon": _labels([f"t{i}" for i in range(5)])})
    pooled = _run(SpecpoolStep(), {"group_label": "pool"}, (abundance, meta))
    stats = values["pool"].reshape(9, 2).T
    assert pooled.data == pytest.approx(stats, abs=1e-5)
