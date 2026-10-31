"""R oracle checks for 0.37 Cramer's V, Jonckheere-Terpstra and varimax."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cramer_v import CramerVStep
from src.task.step.steps.jonckheere_terpstra import JonckheereTerpstraStep
from src.task.step.steps.varimax_rotation import VarimaxRotationStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    output = ctx[params.get("output", step.name)]
    return step.export(ctx), output


def test_r_oracles_for_cramer_v_jt_and_varimax(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    table = np.asarray([[10, 20], [20, 10], [30, 10]], dtype=float)
    values = np.asarray([1, 2, 3, 2, 3, 4, 4, 5, 6, 5, 6, 7], dtype=float)
    groups = np.repeat(np.arange(1, 5), 3).astype(float)
    loadings = np.asarray(
        [[0.8, 0.2], [0.6, 0.4], [0.5, 0.5], [0.3, 0.7], [0.2, 0.8], [0.1, 0.9]],
        dtype=float,
    )
    np.savetxt(tmp_path / "cramer.csv", table, delimiter=",")
    np.savetxt(tmp_path / "jt.csv", np.column_stack([values, groups]), delimiter=",")
    np.savetxt(tmp_path / "loadings.csv", loadings, delimiter=",")
    script = r'''
suppressPackageStartupMessages(library(DescTools))
cm <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "cramer.csv"), header=FALSE))
cat("CRAM", sprintf("%.17g", c(CramerV(cm), chisq.test(cm, correct=FALSE)$statistic)), "\n")
jt <- read.csv(file.path(commandArgs(TRUE)[1], "jt.csv"), header=FALSE)
r <- JonckheereTerpstraTest(jt[[1]], ordered(jt[[2]]), exact=FALSE)
cat("JT", sprintf("%.17g", c(r$statistic, r$p.value)), "\n")
L <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "loadings.csv"), header=FALSE))
v <- varimax(L)
cat("ROT", sprintf("%.17g", as.vector(v$rotmat)), "\n")
cat("LOAD", sprintf("%.17g", as.vector(v$loadings)), "\n")
'''
    proc = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R DescTools not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values_out: dict[str, list[float]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"CRAM", "JT", "ROT", "LOAD"}:
            values_out[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values_out) == {"CRAM", "JT", "ROT", "LOAD"}

    cram_table = _form(
        table,
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1, "r2": 2}, "column": {"c0": 0, "c1": 1}},
    )
    cram, _ = _run(CramerVStep(), {}, [cram_table])
    assert cram["V"] == pytest.approx(values_out["CRAM"][0], rel=1e-12)
    assert cram["chisq"] == pytest.approx(values_out["CRAM"][1], rel=1e-12)

    jt_form = _form(
        np.column_stack([values, groups]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(len(values))},
            "feature": {"value": 0, "group": 1},
        },
    )
    jt, _ = _run(
        JonckheereTerpstraStep(),
        {"value_label": "value", "group_label": "group"},
        [jt_form],
    )
    assert jt["statistic"] == pytest.approx(values_out["JT"][0], rel=1e-12)
    assert jt["p"] == pytest.approx(values_out["JT"][1], rel=1e-12)

    load_form = _form(
        loadings,
        ["variable", "factor"],
        {
            "variable": {f"v{i}": i for i in range(6)},
            "factor": {"f0": 0, "f1": 1},
        },
    )
    rotated, rotated_form = _run(VarimaxRotationStep(), {}, [load_form])
    assert np.asarray(rotated["rotation"]).ravel(order="F") == pytest.approx(
        values_out["ROT"], rel=1e-6
    )
    # R's as.vector() is column-major; Python export is row-major.
    assert np.asarray(rotated_form.data, dtype=float).ravel(order="F") == pytest.approx(
        values_out["LOAD"], rel=1e-7
    )
