"""Authoritative R check for the 0.62 pair confusion matrix / Rand index."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.pair_confusion_matrix import PairConfusionMatrixStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _labels(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        values,
        ["sample", "label"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "label": {"cluster": 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


R_SCRIPT = r"""
library(aricode)
a <- c(0,0,0,1,1,1,2,2,2)
b <- c(0,0,0,1,1,2,2,1,1)
cat(sprintf("%.17g\n", RI(a,b)))
"""


def test_062_pair_confusion_rand_index_matches_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    r_rand = float(proc.stdout.strip())

    result, out = _run(
        PairConfusionMatrixStep(),
        {"label_a": "cluster", "label_b": "cluster"},
        [_labels([0, 0, 0, 1, 1, 1, 2, 2, 2]), _labels([0, 0, 0, 1, 1, 2, 2, 1, 1])],
    )
    matrix = np.asarray(out.data, dtype=np.float64)
    rand_index = (matrix[0, 0] + matrix[1, 1]) / matrix.sum()
    assert rand_index == pytest.approx(r_rand, rel=1e-12)
    assert result["same_cluster_same_label"] == 44
