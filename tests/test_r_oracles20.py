"""R oracle checks for 0.35 reliability and multivariate statistics."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.canonical_correlation import CanonicalCorrelationStep
from src.task.step.steps.cronbach_alpha import CronbachAlphaStep
from src.task.step.steps.runs_test import RunsTestStep


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
    return ctx, step.export(ctx)


def _items():
    return np.asarray(
        [
            [1, 2, 2, 3],
            [2, 3, 3, 4],
            [3, 3, 4, 5],
            [4, 5, 4, 6],
            [5, 5, 6, 7],
            [2, 2, 3, 3],
            [3, 4, 4, 5],
            [4, 4, 5, 6],
            [5, 6, 6, 7],
            [3, 3, 4, 4],
        ],
        dtype=float,
    )


def _canonical_data():
    i = np.arange(1, 21, dtype=float)
    x = np.column_stack([i, np.sin(i)])
    y = np.column_stack(
        [
            i
            + np.asarray(
                [
                    0.1,
                    -0.2,
                    0.3,
                    -0.1,
                    0.2,
                    0,
                    -0.3,
                    0.1,
                    0.2,
                    -0.1,
                    0.3,
                    -0.2,
                    0.1,
                    0,
                    -0.2,
                    0.2,
                    -0.1,
                    0.3,
                    0,
                    -0.3,
                ]
            ),
            np.cos(i),
        ]
    )
    return x, y


def test_r_oracles_for_alpha_cancor_and_runs(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    items = _items()
    x, y = _canonical_data()
    runs = np.asarray([1, 2, 3, 2, 1, 2, 3, 4, 3, 2, 1, 2, 3, 4, 5], dtype=float)
    np.savetxt(tmp_path / "items.csv", items, delimiter=",")
    np.savetxt(tmp_path / "x.csv", x, delimiter=",")
    np.savetxt(tmp_path / "y.csv", y, delimiter=",")
    np.savetxt(tmp_path / "runs.csv", runs, delimiter=",")
    script = r'''
suppressPackageStartupMessages(library(psych))
suppressPackageStartupMessages(library(randtests))
items <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "items.csv"), header=FALSE))
a <- psych::alpha(items, check.keys=FALSE)
cat("ALPHA", sprintf("%.17g", c(a[["total"]][["raw_alpha"]], a[["total"]][["std.alpha"]], a[["total"]][["average_r"]])), "\n")
x <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "x.csv"), header=FALSE))
y <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "y.csv"), header=FALSE))
cc <- cancor(x, y)
cat("CANCOR", sprintf("%.17g", cc[["cor"]]), "\n")
v <- scan(file.path(commandArgs(TRUE)[1], "runs.csv"), quiet=TRUE)
rt <- randtests::runs.test(v)
cat("RUNS", sprintf("%.17g", c(as.numeric(rt[["statistic"]]), rt[["p.value"]], rt[["runs"]], rt[["mu"]], rt[["var"]], rt[["parameter"]][["n1"]], rt[["parameter"]][["n2"]], rt[["parameter"]][["n"]])), "\n")
'''
    proc = subprocess.run(
        ["Rscript", "-e", script, str(tmp_path)],
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R packages psych/randtests not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values: dict[str, list[float]] = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"ALPHA", "CANCOR", "RUNS"}:
            values[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values) == {"ALPHA", "CANCOR", "RUNS"}

    _, alpha = _run(
        CronbachAlphaStep(),
        {},
        [_form(items, ["i1", "i2", "i3", "i4"], "item")],
    )
    assert alpha["raw_alpha"] == pytest.approx(values["ALPHA"][0], rel=1e-12)
    assert alpha["std_alpha"] == pytest.approx(values["ALPHA"][1], rel=1e-12)
    assert alpha["average_r"] == pytest.approx(values["ALPHA"][2], rel=1e-12)

    _, canonical = _run(
        CanonicalCorrelationStep(),
        {},
        [_form(x, ["x1", "x2"], "x"), _form(y, ["y1", "y2"], "y")],
    )
    assert canonical["correlations"] == pytest.approx(values["CANCOR"], rel=1e-12)

    _, runs_info = _run(
        RunsTestStep(),
        {"value_label": "value"},
        [_form(runs, ["value"])],
    )
    expected = values["RUNS"]
    assert runs_info["statistic"] == pytest.approx(expected[0], rel=1e-12)
    assert runs_info["p"] == pytest.approx(expected[1], rel=1e-12)
    assert runs_info["runs"] == int(round(expected[2]))
    assert runs_info["expected_runs"] == pytest.approx(expected[3], rel=1e-12)
    assert runs_info["variance"] == pytest.approx(expected[4], rel=1e-12)
    assert runs_info["n1"] == int(round(expected[5]))
    assert runs_info["n2"] == int(round(expected[6]))
    assert runs_info["n"] == int(round(expected[7]))
