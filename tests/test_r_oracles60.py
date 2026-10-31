"""R oracle for the 0.76 VAR operator."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.var_model import VarModelStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _frame(values):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {"y1": 0, "y2": 1},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _fixture():
    rng = np.random.default_rng(20261105)
    n = 120
    data = np.zeros((n, 2))
    for index in range(1, n):
        data[index] = [
            0.5 * data[index - 1, 0]
            + 0.1 * data[index - 1, 1]
            + rng.normal(0, 0.4),
            0.2 * data[index - 1, 0]
            + 0.4 * data[index - 1, 1]
            + rng.normal(0, 0.4),
        ]
    return data


def test_var_matches_r_vars(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("vars", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip("R vars is not available")

    data = _fixture()
    pd.DataFrame(data, columns=["y1", "y2"]).to_csv(tmp_path / "var.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(vars))
base <- "{tmp_path.as_posix()}"
d <- read.csv(file.path(base, "var.csv"))
f <- VAR(d, p = 1, type = "const")
coefs <- sapply(f$varresult, function(equation) coef(equation))
write.csv(data.frame(term = rownames(coefs), coefs, check.names = FALSE),
          file.path(base, "coefs.csv"), row.names = FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "coefs.csv").set_index("term")

    export, _ = _run(
        VarModelStep(),
        {"lags": 1, "output": "var"},
        [_frame(data)],
    )
    rows = {
        "const": ("const", 0),
        "L1.y1": ("y1.l1", 1),
        "L1.y2": ("y2.l1", 2),
    }
    for equation_index, equation in enumerate(["y1", "y2"]):
        for term, (reference_term, term_index) in rows.items():
            expected = float(reference.loc[reference_term, equation])
            assert export["coef"][term_index][equation_index] == pytest.approx(
                expected, abs=1e-10
            )
