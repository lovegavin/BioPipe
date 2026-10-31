"""R oracle checks for 0.38 Somers' D, Goodman-Kruskal gamma and Kendall's W."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.goodman_kruskal_gamma import GoodmanKruskalGammaStep
from src.task.step.steps.kendall_w import KendallWStep
from src.task.step.steps.somers_d import SomersDStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def test_r_oracles_for_somers_gamma_and_kendall_w(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    table = np.asarray([[10, 5, 2], [6, 12, 4], [3, 7, 15]], dtype=float)
    ratings = np.asarray(
        [[1, 1, 2], [2, 3, 1], [3, 2, 3], [5, 4, 4], [4, 5, 5]], dtype=float
    )
    np.savetxt(tmp_path / "table.csv", table, delimiter=",")
    np.savetxt(tmp_path / "ratings.csv", ratings, delimiter=",")
    script = r'''
suppressPackageStartupMessages(library(DescTools))
tab <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "table.csv"), header=FALSE))
cat("SOMROW", sprintf("%.17g", SomersDelta(tab, direction="row")), "\n")
cat("SOMCOL", sprintf("%.17g", SomersDelta(tab, direction="column")), "\n")
cat("GAMMA", sprintf("%.17g", GoodmanKruskalGamma(tab)), "\n")
x <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "ratings.csv"), header=FALSE))
r <- KendallW(x, correct=FALSE, test=TRUE)
cat("KW", sprintf("%.17g", c(r[["estimate"]], r[["statistic"]], r[["p.value"]])), "\n")
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
    values: dict[str, list[float]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"SOMROW", "SOMCOL", "GAMMA", "KW"}:
            values[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values) == {"SOMROW", "SOMCOL", "GAMMA", "KW"}

    table_form = _form(
        table,
        ["row", "column"],
        {"row": {"low": 0, "mid": 1, "high": 2}, "column": {"a": 0, "b": 1, "c": 2}},
    )
    somers_row = _run(SomersDStep(), {"direction": "row"}, [table_form])
    somers_col = _run(SomersDStep(), {"direction": "column"}, [table_form])
    assert somers_row["D"] == pytest.approx(values["SOMROW"][0], rel=1e-12)
    assert somers_col["D"] == pytest.approx(values["SOMCOL"][0], rel=1e-12)

    gamma = _run(GoodmanKruskalGammaStep(), {}, [table_form])
    assert gamma["gamma"] == pytest.approx(values["GAMMA"][0], rel=1e-12)

    ratings_form = _form(
        ratings,
        ["subject", "rater"],
        {
            "subject": {f"s{i}": i for i in range(5)},
            "rater": {"r1": 0, "r2": 1, "r3": 2},
        },
    )
    w_value = _run(KendallWStep(), {}, [ratings_form])
    assert w_value["W"] == pytest.approx(values["KW"][0], rel=1e-12)
    assert w_value["chisq"] == pytest.approx(values["KW"][1], rel=1e-12)
    assert w_value["p"] == pytest.approx(values["KW"][2], rel=1e-12)
