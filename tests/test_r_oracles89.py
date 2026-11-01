"""R oracle checks for PCNM, Cuzick's trend test and Fisher's alpha."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cuzick import CuzickTestStep
from src.task.step.steps.fisher_alpha import FisherAlphaStep
from src.task.step.steps.pcnm import PcnmStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
d <- as.dist(as.matrix(read.csv(args[1], header = FALSE)))
suppressPackageStartupMessages(library(vegan))
fit <- pcnm(d)
cat("threshold=", format(fit$threshold, digits = 15), "\n", sep = "")
cat("values=", paste(format(fit$values, digits = 15), collapse = ","), "\n", sep = "")
cat("vectors=", paste(format(as.vector(fit$vectors), digits = 15), collapse = ","), "\n", sep = "")
x <- scan(args[2], quiet = TRUE)
g <- factor(readLines(args[3]))
suppressPackageStartupMessages(library(PMCMRplus))
cu <- cuzickTest(x, g, alternative = "two.sided", continuity = FALSE)
cat("cuzick=", format(cu$statistic, digits = 15), ",", format(cu$p.value, digits = 15), "\n", sep = "")
comm <- as.matrix(read.csv(args[4], header = FALSE))
alpha <- fisher.alpha(comm)
cat("alpha=", paste(format(alpha, digits = 15), collapse = ","), "\n", sep = "")
"""

GRID = np.array(
    [[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [0.0, 1.0], [1.0, 1.0], [2.0, 1.0]]
)
GRID_DISTANCE = np.sqrt(((GRID[:, None, :] - GRID[None, :, :]) ** 2).sum(axis=2))
GRID_NAMES = [f"s{index}" for index in range(6)]
CUZICK_X = np.arange(1.0, 16.0)
CUZICK_GROUPS = [str(value) for value in np.repeat([1, 2, 3], 5)]
COMMUNITY = np.array(
    [
        [10.0, 1.0, 0.0, 2.0],
        [0.0, 5.0, 5.0, 0.0],
        [1.0, 1.0, 1.0, 1.0],
        [3.0, 0.0, 0.0, 0.0],
    ]
)
COMMUNITY_NAMES = [f"s{index}" for index in range(4)]
TAXA = ["t1", "t2", "t3", "t4"]


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _labels(names):
    return {name: index for index, name in enumerate(names)}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _parse(lines):
    out = {}
    for line in lines:
        key, _, value = line.partition("=")
        if key:
            out[key] = value
    return out


def test_r_oracles_for_pcnm_cuzick_and_fisher_alpha(tmp_path):
    distance_path = tmp_path / "distance.csv"
    np.savetxt(distance_path, GRID_DISTANCE, delimiter=",")
    x_path = tmp_path / "cuzick_x.txt"
    np.savetxt(x_path, CUZICK_X)
    groups_path = tmp_path / "cuzick_groups.txt"
    groups_path.write_text("\n".join(CUZICK_GROUPS) + "\n", encoding="utf-8")
    community_path = tmp_path / "community.csv"
    np.savetxt(community_path, COMMUNITY, delimiter=",")
    completed = subprocess.run(
        [RSCRIPT, "-e", R_CODE, str(distance_path), str(x_path), str(groups_path), str(community_path)],
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 0, completed.stderr
    values = _parse(completed.stdout.splitlines())

    distance_form = _form(
        GRID_DISTANCE,
        ["sample", "sample_b"],
        {"sample": _labels(GRID_NAMES), "sample_b": _labels(GRID_NAMES)},
    )
    pcnm, _ = _run(PcnmStep(), {}, (distance_form,))
    assert float(values["threshold"]) == pytest.approx(pcnm.info["threshold"], rel=1e-10)
    r_values = np.asarray([float(value) for value in values["values"].split(",")])
    r_positive = r_values[r_values > 1e-10]
    np.testing.assert_allclose(pcnm.info["eigenvalues"], r_positive, atol=1e-8)
    r_vectors = np.asarray([float(value) for value in values["vectors"].split(",")])
    r_vectors = r_vectors.reshape((len(GRID_NAMES), r_positive.size), order="F")
    np.testing.assert_allclose(np.abs(pcnm.data), np.abs(r_vectors), atol=1e-6)

    samples = [f"s{index}" for index in range(15)]
    expression = _form(
        CUZICK_X.reshape(1, 15),
        ["feature", "sample"],
        {"feature": {"x": 0}, "sample": _labels(samples)},
    )
    meta = _form(
        np.repeat([1.0, 2.0, 3.0], 5).reshape(15, 1),
        ["sample", "feature"],
        {"sample": _labels(samples), "feature": {"group": 0}},
    )
    cuzick, _ = _run(CuzickTestStep(), {"group_label": "group"}, (expression, meta))
    expected = [float(value) for value in values["cuzick"].split(",")]
    assert cuzick.data[0, 1] == pytest.approx(expected[0], rel=1e-6)
    assert cuzick.data[0, 2] == pytest.approx(expected[1], rel=1e-5)

    abundance = _form(
        COMMUNITY,
        ["sample", "taxon"],
        {"sample": _labels(COMMUNITY_NAMES), "taxon": _labels(TAXA)},
    )
    alpha, _ = _run(FisherAlphaStep(), {}, (abundance,))
    r_alpha = [float(value) for value in values["alpha"].split(",")]
    assert alpha.data[0, 0] == pytest.approx(r_alpha[0], abs=2e-4)
    assert alpha.data[1, 0] == pytest.approx(r_alpha[1], abs=2e-4)
    assert alpha.data[3, 0] == pytest.approx(r_alpha[3], abs=2e-4)
    assert np.isinf(alpha.data[2, 0])
