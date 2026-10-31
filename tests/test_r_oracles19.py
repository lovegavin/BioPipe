"""R oracle checks for 0.34 paired ROC and Cochran's Q."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.cochran_q import CochranQStep
from src.task.step.steps.roc_comparison import RocComparisonStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}
        self.metadata = {}


def _form(data, names, value_dim="feature"):
    data = np.asarray(data, dtype=np.float64)
    if data.ndim == 1:
        data = data[:, None]
    form = Form(
        data,
        ["sample", value_dim],
        {
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            value_dim: {name: i for i, name in enumerate(names)},
        },
        {"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _roc_fixture():
    rng = np.random.default_rng(42)
    y = np.array([1] * 20 + [0] * 20, dtype=float)
    a = np.r_[rng.normal(1.2, 1.0, 20), rng.normal(0, 1.0, 20)]
    b = 0.7 * a + 0.3 * rng.normal(size=40) + 0.2 * y
    return y, a, b


COCHRAN_ROWS = [
    [1, 1, 1],
    [1, 1, 0],
    [1, 1, 0],
    [1, 0, 1],
    [1, 0, 0],
    [0, 1, 1],
    [0, 1, 0],
    [0, 0, 1],
    [0, 0, 0],
    [0, 0, 0],
]


def test_roc_and_cochran_q_match_r(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript unavailable")
    probe = subprocess.run(
        ["Rscript", "-e", "cat(requireNamespace('pROC',quietly=TRUE) && requireNamespace('DescTools',quietly=TRUE))"],
        capture_output=True,
        text=True,
        check=False,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip(f"R oracle package unavailable: {probe.stdout.strip()}")

    y, a, b = _roc_fixture()
    roc_info = _run(
        RocComparisonStep(),
        {"target_label": "y", "score_a": "a", "score_b": "b"},
        [_form(y, ["y"], "label"), _form(a, ["a"], "score"), _form(b, ["b"], "score")],
    )
    cochran_info = _run(
        CochranQStep(),
        {},
        [_form(COCHRAN_ROWS, ["c1", "c2", "c3"])],
    )
    pd.DataFrame({"y": y, "a": a, "b": b}).to_csv(tmp_path / "roc.csv", index=False)
    wide = pd.DataFrame(COCHRAN_ROWS, columns=["c1", "c2", "c3"])
    long = wide.reset_index().melt(
        id_vars="index", var_name="condition", value_name="resp"
    )
    long = long.rename(columns={"index": "subject"})
    long.to_csv(tmp_path / "cochran.csv", index=False)

    script = r"""
suppressPackageStartupMessages(library(pROC))
suppressPackageStartupMessages(library(DescTools))
d <- read.csv(file.path(commandArgs(TRUE)[1], "roc.csv"))
r1 <- roc(d$y, d$a, direction="<", quiet=TRUE)
r2 <- roc(d$y, d$b, direction="<", quiet=TRUE)
t <- roc.test(r1, r2, method="delong")
cat("AUC", sprintf("%.17g", c(as.numeric(auc(r1)), as.numeric(auc(r2)))), "\n")
cat("TEST", sprintf("%.17g", c(as.numeric(t$statistic), as.numeric(t$p.value))), "\n")
cat("CI", sprintf("%.17g", t$conf.int), "\n")
l <- read.csv(file.path(commandArgs(TRUE)[1], "cochran.csv"))
q <- CochranQTest(resp ~ condition | subject, data=l)
cat("Q", sprintf("%.17g", c(as.numeric(q$statistic), as.numeric(q$p.value))), "\n")
"""
    result = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    parsed = {}
    for line in result.stdout.splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            parsed[parts[0]] = [float(value) for value in parts[1].replace(",", " ").split()]

    assert roc_info["auc_a"] == pytest.approx(parsed["AUC"][0], abs=1e-12)
    assert roc_info["auc_b"] == pytest.approx(parsed["AUC"][1], abs=1e-12)
    assert roc_info["z"] == pytest.approx(parsed["TEST"][0], abs=1e-12)
    assert roc_info["p"] == pytest.approx(parsed["TEST"][1], abs=1e-12)
    assert roc_info["ci_low"] == pytest.approx(parsed["CI"][0], abs=1e-12)
    assert roc_info["ci_high"] == pytest.approx(parsed["CI"][1], abs=1e-12)
    assert cochran_info["statistic"] == pytest.approx(parsed["Q"][0], abs=1e-12)
    assert cochran_info["p"] == pytest.approx(parsed["Q"][1], abs=1e-12)
