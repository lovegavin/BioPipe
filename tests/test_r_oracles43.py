"""Authoritative R checks for the 0.59 clustering metrics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.adjusted_mutual_info import AdjustedMutualInfoStep
from src.task.step.steps.dunn_index import DunnIndexStep
from src.task.step.steps.silhouette_samples import SilhouetteSamplesStep


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
suppressPackageStartupMessages(library(clusterCrit))
suppressPackageStartupMessages(library(aricode))
options(digits=17)
X <- matrix(c(0,0, 0.2,0.1, 0.1,0.2, 5,5, 5.2,5.1, 5.1,5.2), ncol=2, byrow=TRUE)
a <- c(1L,1L,1L,2L,2L,2L)
b <- c(1L,1L,2L,2L,2L,2L)
cat(sprintf("DUNN %.17g\n", intCriteria(X, a, "Dunn")$dunn))
cat(sprintf("AMI %.17g\n", AMI(a,b)))
s <- silhouette(a, dist(X))
for (i in seq_len(nrow(s))) cat(sprintf("SIL %d %.17g\n", i, s[i,3]))
"""


def test_059_clustering_metrics_match_r(tmp_path):
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
    sil = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] == "DUNN":
            values["DUNN"] = float(parts[1])
        elif parts and parts[0] == "AMI":
            values["AMI"] = float(parts[1])
        elif parts and parts[0] == "SIL":
            sil.append(float(parts[2]))
    assert set(values) == {"DUNN", "AMI"}
    assert len(sil) == 6

    _, out = _run(
        DunnIndexStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    assert out.data[0, 0] == pytest.approx(values["DUNN"], rel=1e-6)

    first, second = _labels([0, 0, 0, 1, 1, 1]), _labels([0, 0, 1, 1, 1, 1])
    _, out = _run(
        AdjustedMutualInfoStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [first, second],
    )
    assert out.data[0, 0] == pytest.approx(values["AMI"], rel=1e-6)

    _, out = _run(
        SilhouetteSamplesStep(), {"target_label": "cluster"}, [_matrix(), _labels([0, 0, 0, 1, 1, 1])]
    )
    assert [float(out.data[i, 0]) for i in range(6)] == pytest.approx(sil, rel=1e-6)
