"""Authoritative R checks for 0.56 ordered and umbrella tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.chacko_test import ChackoTestStep
from src.task.step.steps.fligner_wolfe import FlignerWolfeStep
from src.task.step.steps.mack_wolfe import MackWolfeStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _grouped():
    values = np.array(
        [
            1, 2, 3, 4, 5, 6,
            2, 3, 4, 5, 6, 7,
            4, 5, 6, 7, 8, 9,
            3, 4, 5, 6, 7, 8,
        ],
        dtype=float,
    )
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6 + ["D"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(24)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(24)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


R_SCRIPT = r"""
suppressPackageStartupMessages(library(PMCMRplus))
x <- c(1:6, 2:7, 4:9, 3:8)
g <- factor(rep(c("A","B","C","D"), each=6), levels=c("A","B","C","D"))
ch <- chackoTest(x, g)
cat(sprintf("CH %.17g %.17g %.17g\n",
            as.numeric(ch[["statistic"]]),
            as.numeric(ch[["parameter"]]),
            as.numeric(ch[["p.value"]])))
fw <- flignerWolfeTest(x, g, dist="Normal")
cat(sprintf("FW %.17g %.17g\n",
            as.numeric(fw[["statistic"]]),
            as.numeric(fw[["p.value"]])))
mw <- mackWolfeTest(x, g, p=3)
cat(sprintf("MW %.17g %.17g %.17g\n",
            as.numeric(mw[["estimates"]]),
            as.numeric(mw[["statistic"]]),
            as.numeric(mw[["p.value"]])))
"""


def test_056_tests_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"CH", "FW", "MW"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"CH", "FW", "MW"}

    expression, meta = _grouped()
    _, out = _run(ChackoTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data[0, 0] == pytest.approx(values["CH"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["CH"][1])
    assert out.data[0, 2] == pytest.approx(values["CH"][2], rel=1e-8)

    _, out = _run(
        FlignerWolfeStep(),
        {"group_label": "group", "control": "A"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["FW"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["FW"][1], rel=1e-8)

    _, out = _run(
        MackWolfeStep(),
        {"group_label": "group", "peak": "C"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["MW"][0])
    assert out.data[0, 1] == pytest.approx(values["MW"][1], rel=1e-6)
    assert out.data[0, 2] == pytest.approx(values["MW"][2], rel=1e-6)
