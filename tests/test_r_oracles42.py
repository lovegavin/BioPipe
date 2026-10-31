"""Authoritative R checks for the 0.58 clustering metrics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.adjusted_rand_index import AdjustedRandIndexStep
from src.task.step.steps.normalized_mutual_info import NormalizedMutualInfoStep
from src.task.step.steps.silhouette_score import SilhouetteScoreStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _matrix():
    data = [[0, 0], [0.2, 0.1], [0.1, 0.2], [5, 5], [5.2, 5.1], [5.1, 5.2]]
    return _form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(6)},
            "feature": {"f0": 0, "f1": 1},
        },
    )


def _labels(values):
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(cluster))
suppressPackageStartupMessages(library(aricode))
options(digits=17)
X <- matrix(c(0,0, 0.2,0.1, 0.1,0.2, 5,5, 5.2,5.1, 5.1,5.2), ncol=2, byrow=TRUE)
a <- c(0,0,0,1,1,1)
b <- c(0,0,1,1,1,1)
cat(sprintf("SIL %.17g\n", mean(silhouette(a, dist(X))[,3])))
cat(sprintf("ARI %.17g\n", ARI(a,b)))
cat(sprintf("NMI_SUM %.17g\n", NMI(a,b,variant="sum")))
cat(sprintf("NMI_SQRT %.17g\n", NMI(a,b,variant="sqrt")))
cat(sprintf("NMI_MAX %.17g\n", NMI(a,b,variant="max")))
cat(sprintf("NMI_MIN %.17g\n", NMI(a,b,variant="min")))
"""


def test_058_clustering_metrics_match_r(tmp_path):
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
        if parts and parts[0].startswith(("SIL", "ARI", "NMI")):
            values[parts[0]] = float(parts[1])
    assert set(values) == {"SIL", "ARI", "NMI_SUM", "NMI_SQRT", "NMI_MAX", "NMI_MIN"}

    _, out = _run(
        SilhouetteScoreStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    assert out.data[0, 0] == pytest.approx(values["SIL"], rel=1e-6)

    first, second = _labels([0, 0, 0, 1, 1, 1]), _labels([0, 0, 1, 1, 1, 1])
    _, out = _run(
        AdjustedRandIndexStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [first, second],
    )
    assert out.data[0, 0] == pytest.approx(values["ARI"], rel=1e-6)

    for method, key in (
        ("arithmetic", "NMI_SUM"),
        ("geometric", "NMI_SQRT"),
        ("max", "NMI_MAX"),
        ("min", "NMI_MIN"),
    ):
        _, out = _run(
            NormalizedMutualInfoStep(),
            {"label_a": "cluster", "label_b": "cluster", "average_method": method},
            [first, second],
        )
        assert out.data[0, 0] == pytest.approx(values[key], rel=1e-6)
