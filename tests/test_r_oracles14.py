"""Authoritative R checks for the 0.29 regression diagnostics."""
from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.breusch_godfrey import BreuschGodfreyStep
from src.task.step.steps.harvey_collier import HarveyCollierStep
from src.task.step.steps.reset_test import ResetTestStep


RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data):
    if isinstance(data, tuple):
        data = np.column_stack(data)
    labels = {
        "sample": {f"s{i}": i for i in range(data.shape[0])},
        "feature": {"y": 0, "x1": 1, "x2": 2},
    }
    form = Form(np.asarray(data, dtype=np.float64), ["sample", "feature"], labels, {"missing_code": np.nan})
    form.validate()
    return form


def _data():
    rng = np.random.default_rng(29)
    n = 50
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    errors = np.zeros(n)
    for i in range(1, n):
        errors[i] = 0.6 * errors[i - 1] + 0.7 * rng.normal()
    y = 1 + 2 * x1 - 1.5 * x2 + 0.4 * x1 * x1 + errors
    return y, x1, x2


def _run(step, params, data):
    ctx = Ctx(params)
    step.run(ctx, [_form(data)])
    return step.export(ctx)


def _r_values(tmp_path, data):
    y, x1, x2 = data
    path = tmp_path / "diag.csv"
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["y", "x1", "x2"])
        writer.writerows(zip(y, x1, x2))
    script = tmp_path / "oracle.R"
    script.write_text(
        f"""
suppressPackageStartupMessages(library(lmtest))
d <- read.csv("{path.as_posix()}")
fit <- lm(y ~ x1 + x2, data = d)
b <- bgtest(fit, order = 1, type = "Chisq")
cat("BG", sprintf("%.12f", unname(b$statistic)), sprintf("%.12f", unname(b$p.value)),
    unname(b$parameter), "\\n")
r <- resettest(fit, power = 2, type = "fitted")
cat("RESET", sprintf("%.12f", unname(r$statistic)), sprintf("%.12f", unname(r$p.value)),
    paste(unname(r$parameter), collapse = " "), "\\n")
h <- harvtest(fit)
cat("HC", sprintf("%.12f", unname(h$statistic)), sprintf("%.12f", unname(h$p.value)),
    unname(h$parameter), "\\n")
"""
    )
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", str(script)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        if "there is no package called" in proc.stderr:
            pytest.skip(f"R oracle package unavailable: {proc.stderr.strip()[:300]}")
        pytest.fail(f"R 0.29 oracle failed:\n{proc.stderr}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "BG":
            values["BG"] = [float(parts[1]), float(parts[2]), int(float(parts[3]))]
        elif parts[0] == "RESET":
            values["RESET"] = [float(parts[1]), float(parts[2]), int(float(parts[3])), int(float(parts[4]))]
        elif parts[0] == "HC":
            values["HC"] = [float(parts[1]), float(parts[2]), int(float(parts[3]))]
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_diagnostics_match_lmtest(tmp_path):
    data = _data()
    r = _r_values(tmp_path, data)

    bg = _run(BreuschGodfreyStep(), {"response_label": "y", "predictors": ["x1", "x2"], "lags": 1}, data)
    assert bg["lm_statistic"] == pytest.approx(r["BG"][0], abs=1e-8)
    assert bg["lm_p"] == pytest.approx(r["BG"][1], abs=1e-9)
    assert bg["df"] == r["BG"][2]
    assert bg["n"] == 50

    reset = _run(ResetTestStep(), {"response_label": "y", "predictors": ["x1", "x2"], "power": 2}, data)
    assert reset["f_statistic"] == pytest.approx(r["RESET"][0], abs=1e-7)
    assert reset["p"] == pytest.approx(r["RESET"][1], abs=1e-10)
    assert reset["df_num"] == r["RESET"][2]
    assert reset["df_denom"] == r["RESET"][3]

    hc = _run(HarveyCollierStep(), {"response_label": "y", "predictors": ["x1", "x2"]}, data)
    assert hc["statistic"] == pytest.approx(r["HC"][0], abs=1e-8)
    assert hc["p"] == pytest.approx(r["HC"][1], abs=1e-9)
    assert hc["df"] == r["HC"][2]
