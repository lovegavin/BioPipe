"""R oracles for 0.73 Phillips-Perron, DF-GLS and ARCH LM tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.arch_lm import ArchLmStep
from src.task.step.steps.dfgls import DfglsStep
from src.task.step.steps.phillips_perron import PhillipsPerronStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(values):
    values = np.asarray(values, dtype=float).reshape(-1, 1)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {"y": 0},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def test_r_unit_root_and_arch_oracles(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")

    rng = np.random.default_rng(20261102)
    y = np.cumsum(rng.normal(size=120))
    e = rng.standard_t(5, size=200)
    np.savetxt(tmp_path / "series.csv", y.reshape(-1, 1), delimiter=",", header="y", comments="")
    np.savetxt(tmp_path / "resid.csv", e.reshape(-1, 1), delimiter=",", header="e", comments="")

    script = r"""
suppressPackageStartupMessages(library(urca))
suppressPackageStartupMessages(library(FinTS))
base <- commandArgs(TRUE)[1]
y <- read.csv(file.path(base, "series.csv"))$y
e <- read.csv(file.path(base, "resid.csv"))$e
pp <- ur.pp(y, type="Z-t", model="constant", lags="short", use.lag=2)
dg <- ur.ers(y, type="DF-GLS", model="constant", lag.max=2)
at <- ArchTest(e, lags=5)
cat("PP", sprintf("%.17g", as.numeric(pp@teststat)), "\n")
cat("DFGLS", sprintf("%.17g", as.numeric(dg@teststat)), "\n")
cat("ARCH", sprintf("%.17g", as.numeric(at$statistic)),
    sprintf("%.17g", as.numeric(at$p.value)),
    sprintf("%.17g", as.numeric(at$parameter)), "\n")
"""
    proc = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R urca or FinTS not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")

    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"PP", "DFGLS", "ARCH"}:
            values[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values) == {"PP", "DFGLS", "ARCH"}

    pp_result = _run(PhillipsPerronStep(), {"value_label": "y", "lags": 2}, [_form(y)])
    dg_result = _run(DfglsStep(), {"value_label": "y", "lags": 2}, [_form(y)])
    arch_result = _run(ArchLmStep(), {"value_label": "y", "lags": 5}, [_form(e)])

    assert pp_result["statistic"] == pytest.approx(values["PP"][0], abs=1e-6)
    assert dg_result["statistic"] == pytest.approx(values["DFGLS"][0], abs=1e-10)
    assert arch_result["statistic"] == pytest.approx(values["ARCH"][0], abs=1e-10)
    assert arch_result["p"] == pytest.approx(values["ARCH"][1], abs=1e-10)
    assert arch_result["df"] == int(values["ARCH"][2])
