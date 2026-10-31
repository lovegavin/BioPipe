"""Authoritative R checks for 0.51 scale tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.fligner_killeen import FlignerKilleenStep
from src.task.step.steps.mood_scale import MoodScaleStep
from src.task.step.steps.siegel_tukey import SiegelTukeyStep


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


def _grouped(values, groups):
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    n = len(groups)
    expression = _form(
        np.asarray(values, dtype=float).reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(n)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


R_SCRIPT = r"""
suppressPackageStartupMessages(library(PMCMRplus))
a <- c(1,2,3,4,5,6)
b <- c(2,4,6,8,10,12)
c <- c(1,3,5,7,9,11)
f <- stats::fligner.test(list(a,b,c))
m <- stats::mood.test(a,b)
x <- c(1,2,3,4,5)
y <- c(2.5,3.5,4.5,5.5,6.5)
s <- PMCMRplus::siegelTukeyTest(x,y)
cat(sprintf("FL %.17g %.17g\n", as.numeric(f[["statistic"]]), as.numeric(f[["p.value"]])))
cat(sprintf("MO %.17g %.17g\n", as.numeric(m[["statistic"]]), as.numeric(m[["p.value"]])))
cat(sprintf("SI %.17g %.17g\n", as.numeric(s[["statistic"]]), as.numeric(s[["p.value"]])))
"""


def test_051_scale_tests_match_r(tmp_path):
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
        if parts and parts[0] in {"FL", "MO", "SI"}:
            values[parts[0]] = (float(parts[1]), float(parts[2]))
    assert set(values) == {"FL", "MO", "SI"}

    a = [1, 2, 3, 4, 5, 6]
    b = [2, 4, 6, 8, 10, 12]
    c = [1, 3, 5, 7, 9, 11]
    expression, meta = _grouped(a + b + c, ["A"] * 6 + ["B"] * 6 + ["C"] * 6)
    _, out = _run(FlignerKilleenStep(), {"group_label": "group"}, [expression, meta])
    assert out.data[0, 0] == pytest.approx(values["FL"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["FL"][1], rel=1e-6)

    expression, meta = _grouped(a + b, ["A"] * 6 + ["B"] * 6)
    _, out = _run(
        MoodScaleStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["MO"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["MO"][1], rel=1e-6)

    x = [1, 2, 3, 4, 5]
    y = [2.5, 3.5, 4.5, 5.5, 6.5]
    expression, meta = _grouped(x + y, ["A"] * 5 + ["B"] * 5)
    _, out = _run(
        SiegelTukeyStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["SI"][0], rel=1e-12)
    assert out.data[0, 1] == pytest.approx(values["SI"][1], rel=1e-6)
