"""R external oracle for Holm and Benjamini-Yekutieli correction."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.by_adjust import ByAdjustStep
from src.task.step.steps.holm_adjust import HolmAdjustStep

RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, form):
    ctx = Ctx({})
    step.run(ctx, [form])
    return ctx[step.name]


def _run_r(tmp_path, script):
    path = tmp_path / "oracle.R"
    path.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [RSCRIPT, "--no-save", "--no-restore", str(path)],
        cwd=tmp_path, capture_output=True, text=True, timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(f"R oracle failed\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}")


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_holm_and_by_match_r_p_adjust(tmp_path):
    pvalues = np.array([0.01, 0.04, 0.03, 0.005, 0.2, 0.0001], dtype=float)
    form = _form(
        pvalues.reshape(-1, 1), ["feature", "pvalue"],
        {"feature": {f"g{i}": i for i in range(len(pvalues))}, "pvalue": {"p": 0}},
    )
    holm = _run(HolmAdjustStep(), form).data[:, 0].astype(float)
    by = _run(ByAdjustStep(), form).data[:, 0].astype(float)

    pd.DataFrame({"p": pvalues}).to_csv(tmp_path / "p.csv", index=False)
    _run_r(
        tmp_path,
        "p <- read.csv('p.csv')$p\n"
        "write.csv(data.frame(holm=p.adjust(p, method='holm'), "
        "by=p.adjust(p, method='BY')), 'adjusted.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "adjusted.csv")
    assert holm == pytest.approx(expected["holm"].to_numpy(), rel=1e-5, abs=1e-7)
    assert by == pytest.approx(expected["by"].to_numpy(), rel=1e-5, abs=1e-7)
