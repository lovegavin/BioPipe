"""R oracle for the 0.77 power operators."""
from __future__ import annotations

import shutil
import subprocess

import pandas as pd
import pytest

from src.task.step.steps.power_anova import PowerAnovaStep
from src.task.step.steps.power_prop_test import PowerPropTestStep
from src.task.step.steps.power_t_test import PowerTTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _power(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return step.export(ctx)["power"]


def test_power_operators_match_r_pwr(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("pwr", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip("R pwr is not available")

    script = f"""
suppressPackageStartupMessages(library(pwr))
base <- "{tmp_path.as_posix()}"
two <- pwr.t.test(n = 64, d = 0.5, sig.level = 0.05,
                  type = "two.sample", alternative = "two.sided")$power
paired <- pwr.t.test(n = 64, d = 0.5, sig.level = 0.05,
                     type = "paired", alternative = "two.sided")$power
prop <- pwr.2p.test(h = ES.h(0.6, 0.4), n = 100, sig.level = 0.05,
                    alternative = "two.sided")$power
anova <- pwr.anova.test(k = 4, n = 40, f = 0.25, sig.level = 0.05)$power
write.csv(data.frame(name = c("two", "paired", "prop", "anova"),
                     power = c(two, paired, prop, anova)),
          file.path(base, "power.csv"), row.names = FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "power.csv").set_index("name")["power"]

    assert _power(PowerTTestStep(), {"effect_size": 0.5, "nobs1": 64}) == pytest.approx(
        float(reference["two"]), abs=1e-9
    )
    assert _power(
        PowerTTestStep(), {"test": "paired", "effect_size": 0.5, "nobs1": 64}
    ) == pytest.approx(float(reference["paired"]), abs=1e-9)
    assert _power(
        PowerPropTestStep(),
        {"p1": 0.6, "p2": 0.4, "nobs1": 100, "nobs2": 100},
    ) == pytest.approx(float(reference["prop"]), abs=1e-9)
    assert _power(
        PowerAnovaStep(),
        {"effect_size": 0.25, "n_per_group": 40, "k_groups": 4},
    ) == pytest.approx(float(reference["anova"]), abs=1e-9)
