"""R oracles for 0.75 correspondence analysis and Tobit regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.correspondence_analysis import CorrespondenceAnalysisStep
from src.task.step.steps.tobit import TobitStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _tobit_form(frame):
    form = Form(
        data=frame.to_numpy(dtype=float),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(len(frame))},
            "feature": {name: index for index, name in enumerate(frame.columns)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _ca_form(frame):
    form = Form(
        data=frame.to_numpy(dtype=float),
        dims=["row", "column"],
        labels={
            "row": {name: index for index, name in enumerate(frame.index)},
            "column": {name: index for index, name in enumerate(frame.columns)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _rscript(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        [
            "Rscript",
            "-e",
            'cat(requireNamespace("censReg", quietly=TRUE) && '
            'requireNamespace("ca", quietly=TRUE))',
        ],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip("R packages censReg and ca are not available")
    return "Rscript"


def test_ca_and_tobit_match_r(tmp_path):
    rscript = _rscript(tmp_path)
    rng = np.random.default_rng(20261103)
    n = 60
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    y = 1.2 + 0.9 * x1 - 0.6 * x2 + rng.normal(scale=1.1, size=n)
    tobit_frame = pd.DataFrame({"y": np.maximum(y, 0.0), "x1": x1, "x2": x2})
    tobit_frame.to_csv(tmp_path / "tobit_input.csv", index=False)
    ca_frame = pd.DataFrame(
        [[10, 20, 30], [20, 40, 20], [30, 10, 10], [15, 25, 35]],
        index=["r1", "r2", "r3", "r4"],
        columns=["c1", "c2", "c3"],
    )
    ca_frame.to_csv(tmp_path / "ca_input.csv")

    script = f"""
suppressPackageStartupMessages(library(censReg))
suppressPackageStartupMessages(library(ca))
base <- "{tmp_path.as_posix()}"
d <- read.csv(file.path(base, "tobit_input.csv"))
fit <- censReg(y ~ x1 + x2, left = 0, data = d)
out <- data.frame(
  term = c("(Intercept)", "x1", "x2"),
  coef = coef(fit)[1:3],
  se = stdEr(fit)[1:3]
)
write.csv(out, file.path(base, "tobit_fit.csv"), row.names = FALSE)
write.csv(data.frame(loglik = as.numeric(logLik(fit))),
          file.path(base, "tobit_loglik.csv"), row.names = FALSE)
m <- as.matrix(read.csv(file.path(base, "ca_input.csv"),
                        row.names = 1, check.names = FALSE))
res <- ca(m)
write.csv(data.frame(sv = res$sv), file.path(base, "ca_sv.csv"), row.names = FALSE)
write.csv(res$rowcoord, file.path(base, "ca_rows.csv"))
write.csv(res$colcoord, file.path(base, "ca_cols.csv"))
"""
    result = subprocess.run([rscript, "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

    tobit_r = pd.read_csv(tmp_path / "tobit_fit.csv")
    tobit = _run(
        TobitStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "fit"},
        [_tobit_form(tobit_frame)],
    )
    assert tobit["coef"] == pytest.approx(tobit_r["coef"].tolist(), abs=2e-6)
    assert tobit["se"] == pytest.approx(tobit_r["se"].tolist(), abs=2e-6)
    loglik = float(pd.read_csv(tmp_path / "tobit_loglik.csv")["loglik"].iloc[0])
    assert tobit["loglik"] == pytest.approx(loglik, abs=1e-8)

    ca = _run(
        CorrespondenceAnalysisStep(),
        {"output": "ca"},
        [_ca_form(ca_frame)],
    )
    sv = pd.read_csv(tmp_path / "ca_sv.csv")["sv"].to_numpy()
    rows = pd.read_csv(tmp_path / "ca_rows.csv", index_col=0).to_numpy()
    cols = pd.read_csv(tmp_path / "ca_cols.csv", index_col=0).to_numpy()
    assert ca["singular_values"] == pytest.approx(sv, rel=1e-12)
    np.testing.assert_allclose(
        ca["standard_row_coordinates"], rows, rtol=1e-12, atol=1e-14
    )
    np.testing.assert_allclose(
        ca["standard_column_coordinates"], cols, rtol=1e-12, atol=1e-14
    )
