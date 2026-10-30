"""R oracle checks for 0.36 factorability diagnostics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.bartlett_sphericity import BartlettSphericityStep
from src.task.step.steps.kmo_test import KmoTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, names):
    data = np.asarray(data, dtype=np.float64)
    form = Form(
        data,
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _data():
    return np.asarray(
        [
            [1, 2, 2, 1],
            [2, 3, 3, 2],
            [3, 4, 4, 2],
            [4, 5, 4, 3],
            [5, 6, 5, 4],
            [2, 2, 3, 2],
            [3, 3, 4, 3],
            [4, 4, 5, 4],
            [5, 5, 6, 5],
            [3, 4, 4, 3],
            [2, 3, 2, 2],
            [4, 4, 5, 4],
        ],
        dtype=float,
    )


def test_r_oracles_for_kmo_and_bartlett(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    data = _data()
    np.savetxt(tmp_path / "data.csv", data, delimiter=",")
    script = r'''
suppressPackageStartupMessages(library(psych))
x <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "data.csv"), header=FALSE))
r <- cor(x)
k <- psych::KMO(r)
b <- psych::cortest.bartlett(r, n=nrow(x))
cat("KMO", sprintf("%.17g", c(k[["MSA"]], k[["MSAi"]])), "\n")
cat("BART", sprintf("%.17g", c(b[["chisq"]], b[["df"]], b[["p.value"]])), "\n")
'''
    proc = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R package psych not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values: dict[str, list[float]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"KMO", "BART"}:
            values[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values) == {"KMO", "BART"}
    kmo = _run(KmoTestStep(), {}, [_form(data, ["v1", "v2", "v3", "v4"])])
    assert kmo["msa_overall"] == pytest.approx(values["KMO"][0], rel=1e-12)
    assert list(kmo["msa"].values()) == pytest.approx(values["KMO"][1:], rel=1e-12)
    bart = _run(
        BartlettSphericityStep(), {}, [_form(data, ["v1", "v2", "v3", "v4"])]
    )
    assert bart["chisq"] == pytest.approx(values["BART"][0], rel=1e-12)
    assert bart["df"] == int(round(values["BART"][1]))
    assert bart["p"] == pytest.approx(values["BART"][2], rel=1e-12)
