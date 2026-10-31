"""R oracle checks for 0.72 Theil U, DFBETAS and COVRATIO."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.covratio import CovratioStep
from src.task.step.steps.dfbetas import DfbetasStep
from src.task.step.steps.theil_u import TheilUStep


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
    return step.export(ctx), ctx[params.get("output", step.name)]


def test_r_oracles_for_072(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    data = np.asarray([
        [3, 1, 2], [5, 2, 1], [4, 3, 4], [8, 4, 3],
        [7, 5, 6], [10, 6, 5], [9, 7, 8], [12, 8, 7],
    ], dtype=float)
    table = np.asarray([[10, 20], [30, 40]], dtype=float)
    np.savetxt(tmp_path / "reg.csv", data, delimiter=",")
    np.savetxt(tmp_path / "table.csv", table, delimiter=",")
    script = r"""
d <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "reg.csv"), header=FALSE))
m <- lm(d[,1] ~ d[,2] + d[,3])
cat("DFB", sprintf("%.17g", as.vector(t(dfbetas(m)))), "\n")
cat("COV", sprintf("%.17g", as.vector(covratio(m))), "\n")
t <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "table.csv"), header=FALSE))
cat("THEIL", sprintf("%.17g", c(
  DescTools::UncertCoef(t, direction="row"),
  DescTools::UncertCoef(t, direction="column"),
  DescTools::UncertCoef(t, direction="symmetric")
)), "\n")
"""
    proc = subprocess.run(["Rscript", "-e", script, str(tmp_path)], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R DescTools not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"DFB", "COV", "THEIL"}:
            values[parts[0]] = [float(v) for v in parts[1:]]
    assert set(values) == {"DFB", "COV", "THEIL"}

    reg = _form(
        data,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"y": 0, "x1": 1, "x2": 2}},
    )
    _, dfb = _run(DfbetasStep(), {"response": "y"}, [reg])
    np.testing.assert_allclose(dfb.data, np.asarray(values["DFB"]).reshape(8, 3), rtol=2e-6, atol=2e-6)

    _, cov = _run(CovratioStep(), {"response": "y"}, [reg])
    np.testing.assert_allclose(cov.data[:, 0], values["COV"], rtol=2e-6, atol=2e-6)

    table_form = _form(
        table,
        ["row", "column"],
        {"row": {"r0": 0, "r1": 1}, "column": {"c0": 0, "c1": 1}},
    )
    result, _ = _run(TheilUStep(), {}, [table_form])
    assert result["u_row_given_column"] == pytest.approx(values["THEIL"][0], rel=2e-6)
    assert result["u_column_given_row"] == pytest.approx(values["THEIL"][1], rel=2e-6)
    assert result["u_symmetric"] == pytest.approx(values["THEIL"][2], rel=2e-6)
