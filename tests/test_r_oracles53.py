"""Authoritative R checks for 0.69 approximate entropy and Hurst exponent."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.approx_entropy import ApproxEntropyStep
from src.task.step.steps.hurst_exponent import HurstExponentStep


class Ctx(dict):
    def __init__(self):
        super().__init__()
        self.step_params = {}


def _run(step, values):
    ctx = Ctx()
    ctx.step_params = {"value_label": "value"}
    form = Form(
        np.asarray(values, dtype=np.float64).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(len(values))}, "feature": {"value": 0}},
        {"missing_code": np.nan},
    )
    form.validate()
    step.run(ctx, [form])
    return step.export(ctx)


def _fixture():
    return np.round(np.sin(np.linspace(0, 8 * np.pi, 100)) + 0.1 * np.arange(100) / 100, 1)


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript is unavailable")
def test_entropy_and_hurst_match_pracma(tmp_path):
    values = _fixture()
    data = tmp_path / "values.csv"
    np.savetxt(data, values, fmt="%.17g")
    oracle = tmp_path / "entropy.R"
    oracle.write_text(
        "suppressPackageStartupMessages(library(pracma))\n"
        "v <- scan('" + str(data) + "', quiet=TRUE)\n"
        "cat(sprintf('%.17g', approx_entropy(v)), '\\n')\n"
        "cat(sprintf('%.17g', hurstexp(v, display=FALSE)$Hs), '\\n')\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["Rscript", str(oracle)],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = [float(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(expected) == 2, proc.stdout + proc.stderr

    approx = _run(ApproxEntropyStep(), values)
    hurst = _run(HurstExponentStep(), values)
    assert approx["approx_entropy"] == pytest.approx(expected[0], rel=1e-10)
    assert hurst["hurst"] == pytest.approx(expected[1], rel=1e-10)
