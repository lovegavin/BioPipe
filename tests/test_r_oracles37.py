"""Authoritative R checks for the 0.53 scale and outlier tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.ansari_bradley import AnsariBradleyStep
from src.task.step.steps.chisq_out_test import ChiSquareOutTestStep


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


def _series(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(n)}, "feature": {"value": 0}},
    )


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
suppressPackageStartupMessages(library(outliers))
options(digits=17)
a <- ansari.test(c(1,2,3,4,5), c(1,4,9,16,25), exact=FALSE)
cat(sprintf("AB %.17g %.17g\n", as.numeric(a[["statistic"]]), as.numeric(a[["p.value"]])))
b <- chisq.out.test(c(1,2,3,4,5,100))
cat(sprintf("CH %.17g %.17g\n", as.numeric(b[["statistic"]]), as.numeric(b[["p.value"]])))
c <- chisq.out.test(c(1,2,3,4,5,100), opposite=TRUE)
cat(sprintf("CO %.17g %.17g\n", as.numeric(c[["statistic"]]), as.numeric(c[["p.value"]])))
"""


def test_053_tests_match_r(tmp_path):
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
        if parts and parts[0] in {"AB", "CH", "CO"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"AB", "CH", "CO"}

    expression, meta = _grouped(
        [1, 2, 3, 4, 5, 1, 4, 9, 16, 25],
        ["A"] * 5 + ["B"] * 5,
    )
    _, out = _run(
        AnsariBradleyStep(),
        {"group_label": "group", "group_a": "A", "group_b": "B"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["AB"][0], rel=1e-6)
    assert out.data[0, 2] == pytest.approx(values["AB"][1], rel=1e-6)

    _, out = _run(ChiSquareOutTestStep(), {"value_label": "value"}, [_series([1, 2, 3, 4, 5, 100])])
    assert out.data[0, 0] == pytest.approx(values["CH"][0], rel=1e-6)
    assert out.data[1, 0] == pytest.approx(values["CH"][1], rel=1e-6)

    _, out = _run(
        ChiSquareOutTestStep(),
        {"value_label": "value", "opposite": True},
        [_series([1, 2, 3, 4, 5, 100])],
    )
    assert out.data[0, 0] == pytest.approx(values["CO"][0], rel=1e-6)
    assert out.data[1, 0] == pytest.approx(values["CO"][1], rel=1e-6)
