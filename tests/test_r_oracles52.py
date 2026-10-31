"""Authoritative R checks for 0.68 inter-rater agreement coefficients."""
from __future__ import annotations

import shutil
import subprocess

import pytest

from src.core import Form
from src.task.step.steps.brennan_prediger import BrennanPredigerStep
from src.task.step.steps.conger_kappa import CongerKappaStep
from src.task.step.steps.gwet_ac1 import GwetAc1Step

RATINGS = [
    [1, 2, 3, 3],
    [2, 1, 1, 2],
    [2, 3, 3, 2],
    [1, 1, 2, 3],
    [3, 1, 2, 2],
]


class Ctx(dict):
    def __init__(self):
        super().__init__()
        self.step_params = {}


def _run(step, ratings):
    class LocalCtx(Ctx):
        pass

    ctx = LocalCtx()
    form = Form(
        __import__("numpy").asarray(ratings, dtype=float),
        ["subject", "rater"],
        {"subject": {f"s{i}": i for i in range(len(ratings))}, "rater": {f"r{i}": i for i in range(len(ratings[0]))}},
        {"missing_code": float("nan")},
    )
    form.validate()
    step.run(ctx, [form])
    return step.export(ctx)


@pytest.mark.skipif(shutil.which("Rscript") is None, reason="Rscript is unavailable")
def test_agreement_coefficients_match_irrCAC(tmp_path):
    oracle = tmp_path / "agreement.R"
    oracle.write_text(
        "suppressPackageStartupMessages(library(irrCAC))\n"
        "m <- as.matrix(read.csv('" + str(tmp_path / "ratings.csv") + "', header=FALSE))\n"
        "cat(sprintf('%.17g', gwet.ac1.raw(m)$est$coeff.val), '\\n')\n"
        "cat(sprintf('%.17g', bp.coeff.raw(m)$est$coeff.val), '\\n')\n"
        "cat(sprintf('%.17g', conger.kappa.raw(m)$est$coeff.val), '\\n')\n",
        encoding="utf-8",
    )
    (tmp_path / "ratings.csv").write_text(
        "\n".join(",".join(str(int(v)) for v in row) for row in RATINGS) + "\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        ["Rscript", str(oracle)],
        check=True,
        capture_output=True,
        text=True,
    )
    expected = [float(line) for line in proc.stdout.splitlines() if line.strip()]
    assert len(expected) == 3, proc.stdout + proc.stderr

    assert _run(GwetAc1Step(), RATINGS)["gwet_ac1"] == pytest.approx(expected[0], abs=1e-5)
    assert _run(BrennanPredigerStep(), RATINGS)["brennan_prediger"] == pytest.approx(expected[1], abs=1e-5)
    assert _run(CongerKappaStep(), RATINGS)["conger_kappa"] == pytest.approx(expected[2], abs=1e-5)
