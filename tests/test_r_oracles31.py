"""Authoritative R checks for 0.47 post-hoc and change-point operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.nemenyi_test import NemenyiTestStep
from src.task.step.steps.pettitt_test import PettittTestStep
from src.task.step.steps.scheffe_test import ScheffeTestStep


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
    values = np.array([1, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13], dtype=float)
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(18)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(18)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def _series():
    values = np.array(
        [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18],
        dtype=float,
    )
    return _form(
        values.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(20)}, "feature": {"value": 0}},
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
suppressPackageStartupMessages(library(trend))
x <- c(1,2,3,4,5,6, 4,5,6,7,8,9, 8,9,10,11,12,13)
g <- factor(rep(c("A","B","C"), each=6))
s <- ScheffeTest(aov(x ~ g))[[1]]
for (i in seq_len(nrow(s))) {
  cat(sprintf("SCH %s %.17g %.17g %.17g %.17g\n",
              rownames(s)[i], s[i,1], s[i,2], s[i,3], s[i,4]))
}
n <- NemenyiTest(x, g)[[1]]
for (i in seq_len(nrow(n))) {
  cat(sprintf("NEM %s %.17g %.17g\n", rownames(n)[i], n[i,1], n[i,2]))
}
y <- c(1,2,3,4,5,6,7,8,9,10, 9,10,11,12,13,14,15,16,17,18)
p <- pettitt.test(y)
cat(sprintf("PET %.17g %.17g\n", as.numeric(p[["statistic"]]), as.numeric(p[["p.value"]])))
cat(sprintf("K %s\n", paste(as.integer(p[["estimate"]]), collapse=",")))
"""


def test_047_operators_match_r(tmp_path):
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

    scheffe = {}
    nemenyi = {}
    pettitt = None
    points = []
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "SCH":
            scheffe[parts[1]] = tuple(float(value) for value in parts[2:])
        elif parts[0] == "NEM":
            nemenyi[parts[1]] = tuple(float(value) for value in parts[2:])
        elif parts[0] == "PET":
            pettitt = tuple(float(value) for value in parts[1:])
        elif parts[0] == "K":
            points = [int(value) for value in parts[1].split(",")]

    assert set(scheffe) == {"B-A", "C-A", "C-B"}
    assert set(nemenyi) == {"B-A", "C-A", "C-B"}
    assert pettitt is not None

    expression, meta = _grouped()
    _, out = _run(ScheffeTestStep(), {"group_label": "group"}, [expression, meta])
    expected_scheffe = [scheffe[name] for name in ("B-A", "C-A", "C-B")]
    assert np.allclose(
        out.data[:, 0],
        [-row[0] for row in expected_scheffe],
        rtol=1e-6,
        atol=1e-7,
    )
    assert np.allclose(
        out.data[:, 1],
        [row[3] for row in expected_scheffe],
        rtol=1e-6,
        atol=1e-8,
    )
    assert np.allclose(
        out.data[:, 2:4],
        [[-row[2], -row[1]] for row in expected_scheffe],
        rtol=1e-6,
        atol=1e-7,
    )

    _, out = _run(NemenyiTestStep(), {"group_label": "group"}, [expression, meta])
    expected_nemenyi = [nemenyi[name] for name in ("B-A", "C-A", "C-B")]
    assert np.allclose(
        out.data[:, 0],
        [-row[0] for row in expected_nemenyi],
        rtol=1e-6,
        atol=1e-7,
    )
    assert np.allclose(
        out.data[:, 1],
        [row[1] for row in expected_nemenyi],
        rtol=1e-6,
        atol=1e-8,
    )

    result, _ = _run(PettittTestStep(), {"value_label": "value"}, [_series()])
    assert result["U"] == pytest.approx(pettitt[0], rel=1e-9)
    assert result["p"] == pytest.approx(pettitt[1], rel=1e-9)
    assert result["change_points"] == points
