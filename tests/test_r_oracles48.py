"""Authoritative R check for 0.64 risk ratio, odds ratio, and Cohen's h."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.cohens_h import CohensHStep
from src.task.step.steps.odds_ratio import OddsRatioStep
from src.task.step.steps.risk_ratio import RiskRatioStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _table(values):
    data = np.asarray(values, dtype=np.float64)
    form = Form(
        data,
        ["row", "col"],
        {"row": {"exposed": 0, "unexposed": 1}, "col": {"event": 0, "no_event": 1}},
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


R_SCRIPT = r"""
library(pwr)
a <- 18; b <- 12; c <- 10; d <- 20
n1 <- a + b; n2 <- c + d
p1 <- a / n1; p2 <- c / n2
rr <- p1 / p2
se_rr <- sqrt(1/a - 1/n1 + 1/c - 1/n2)
z <- qnorm(0.975)
cat(sprintf("%.17g\n", rr))
cat(sprintf("%.17g\n", exp(log(rr) - z * se_rr)))
cat(sprintf("%.17g\n", exp(log(rr) + z * se_rr)))
or <- a * d / (b * c)
se_or <- sqrt(1/a + 1/b + 1/c + 1/d)
cat(sprintf("%.17g\n", or))
cat(sprintf("%.17g\n", exp(log(or) - z * se_or)))
cat(sprintf("%.17g\n", exp(log(or) + z * se_or)))
h <- ES.h(p1, p2)
se_h <- sqrt(1/n1 + 1/n2)
cat(sprintf("%.17g\n", h))
cat(sprintf("%.17g\n", h - z * se_h))
cat(sprintf("%.17g\n", h + z * se_h))
"""


def test_064_effect_sizes_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr)
    values = [float(line) for line in proc.stdout.strip().splitlines()]

    table = _table([[18, 12], [10, 20]])
    _, rr = _run(RiskRatioStep(), {}, [table])
    _, odds = _run(OddsRatioStep(), {}, [table])
    _, h = _run(CohensHStep(), {}, [table])

    assert rr.data[0, 0] == pytest.approx(values[0], rel=1e-12)
    assert rr.data[0, 1] == pytest.approx(values[1], rel=1e-12)
    assert rr.data[0, 2] == pytest.approx(values[2], rel=1e-12)
    assert odds.data[0, 0] == pytest.approx(values[3], rel=1e-12)
    assert odds.data[0, 1] == pytest.approx(values[4], rel=1e-12)
    assert odds.data[0, 2] == pytest.approx(values[5], rel=1e-12)
    assert h.data[0, 0] == pytest.approx(values[6], rel=1e-12)
    assert h.data[0, 1] == pytest.approx(values[7], rel=1e-12)
    assert h.data[0, 2] == pytest.approx(values[8], rel=1e-12)
