"""Authoritative R checks for 0.52 skewness, GOF, and outlier tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.agostino_skewness import AgostinoSkewnessStep
from src.task.step.steps.chi_square_gof import ChiSquareGofStep
from src.task.step.steps.cochran_c_test import CochranCTestStep


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


def _counts(values):
    n = len(values)
    return _form(
        np.asarray(values, dtype=float).reshape(-1, 1),
        ["category", "feature"],
        {"category": {f"c{i}": i for i in range(n)}, "feature": {"count": 0}},
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
suppressPackageStartupMessages(library(moments))
suppressPackageStartupMessages(library(outliers))
x <- c(1,2,3,4,5,6,7,8,9,20)
a <- agostino.test(x)
cat(sprintf("AG %.17g %.17g %.17g\n",
            as.numeric(a[["statistic"]][["skew"]]),
            as.numeric(a[["statistic"]][["z"]]),
            as.numeric(a[["p.value"]])))
obs <- c(10,20,30,40)
g <- chisq.test(obs)
cat(sprintf("CH %.17g %.17g\n", as.numeric(g[["statistic"]]), as.numeric(g[["p.value"]])))
values <- c(1,2,3,4,5,2,4,6,8,10,10,20,30,40,50)
groups <- factor(rep(c("A","B","C"), each=5))
d <- data.frame(value=values, group=groups)
cc <- cochran.test(value ~ group, data=d)
cat(sprintf("CO %.17g %.17g\n", as.numeric(cc[["statistic"]]), as.numeric(cc[["p.value"]])))
"""


def test_052_tests_match_r(tmp_path):
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
        if parts and parts[0] in {"AG", "CH", "CO"}:
            values[parts[0]] = tuple(float(value) for value in parts[1:])
    assert set(values) == {"AG", "CH", "CO"}

    _, out = _run(
        AgostinoSkewnessStep(),
        {"value_label": "value"},
        [_series([1, 2, 3, 4, 5, 6, 7, 8, 9, 20])],
    )
    assert out.data[0, 0] == pytest.approx(values["AG"][0], rel=1e-6)
    assert out.data[1, 0] == pytest.approx(values["AG"][1], rel=1e-6)
    assert out.data[2, 0] == pytest.approx(values["AG"][2], rel=1e-6)

    _, out = _run(ChiSquareGofStep(), {"count_label": "count"}, [_counts([10, 20, 30, 40])])
    assert out.data[0, 0] == pytest.approx(values["CH"][0], rel=1e-6)
    assert out.data[2, 0] == pytest.approx(values["CH"][1], rel=1e-6)

    expression, meta = _grouped(
        [1, 2, 3, 4, 5, 2, 4, 6, 8, 10, 10, 20, 30, 40, 50],
        ["A"] * 5 + ["B"] * 5 + ["C"] * 5,
    )
    _, out = _run(
        CochranCTestStep(),
        {"group_label": "group", "value_label": "value"},
        [expression, meta],
    )
    assert out.data[0, 0] == pytest.approx(values["CO"][0], rel=1e-6)
    assert out.data[1, 0] == pytest.approx(values["CO"][1], rel=1e-6)
