"""Authoritative R checks for 0.50 Levene and Brown-Forsythe tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.brown_forsythe import BrownForsytheStep
from src.task.step.steps.levene_test import LeveneTestStep


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
        [1, 2, 3, 4, 100, 2, 4, 6, 8, 20, 10, 20, 30, 40, 50],
        dtype=float,
    )
    groups = ["A"] * 5 + ["B"] * 5 + ["C"] * 5
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(15)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(15)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
x <- c(1,2,3,4,100, 2,4,6,8,20, 10,20,30,40,50)
g <- factor(rep(c("A","B","C"), each=5))
for (ctr in c("mean","median")) {
  r <- LeveneTest(x, g, center=ctr)
  cat(sprintf("LEV_%s %.17g %.17g\n",
              ctr,
              as.numeric(r[["F value"]][1]),
              as.numeric(r[["Pr(>F)"]][1])))
}
"""


def test_050_variance_tests_match_r(tmp_path):
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
        if parts and parts[0] in {"LEV_mean", "LEV_median"}:
            values[parts[0]] = (float(parts[1]), float(parts[2]))
    assert set(values) == {"LEV_mean", "LEV_median"}

    expression, meta = _grouped()
    _, out = _run(LeveneTestStep(), {"group_label": "group"}, [expression, meta])
    assert out.data[0, 0] == pytest.approx(values["LEV_mean"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["LEV_mean"][1], rel=1e-6)

    _, out = _run(BrownForsytheStep(), {"group_label": "group"}, [expression, meta])
    assert out.data[0, 0] == pytest.approx(values["LEV_median"][0], rel=1e-6)
    assert out.data[0, 1] == pytest.approx(values["LEV_median"][1], rel=1e-6)
