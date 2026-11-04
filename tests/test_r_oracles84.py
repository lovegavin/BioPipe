"""R oracle for classical seasonal decomposition."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.seasonal_decompose import SeasonalDecomposeStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _series(values):
    data = np.asarray(values, dtype=np.float64).reshape(-1, 1)
    return Form(
        data=data,
        dims=["sample", "feature"],
        labels={
            "sample": {f"t{i}": i for i in range(data.shape[0])},
            "feature": {"value": 0},
        },
        info={"missing_code": np.nan},
    )


def _run(values, period, model):
    step = SeasonalDecomposeStep()
    ctx = Ctx({"value_label": "value", "period": period, "model": model})
    step.run(ctx, [_series(values)])
    return ctx[step.name], step.export(ctx)


def _r_decompose(values, period, model, tmp_path):
    path = tmp_path / "series.csv"
    script = tmp_path / "decompose.R"
    np.savetxt(path, np.asarray(values), delimiter=",", header="value", comments="")
    script.write_text(
        f"""
x <- read.csv("{path}", check.names=FALSE)$value
dec <- decompose(ts(x, frequency={period}), type="{model}")
cat(paste(sprintf("%.17g", dec$trend), collapse=","), "\\n")
cat(paste(sprintf("%.17g", dec$seasonal), collapse=","), "\\n")
cat(paste(sprintf("%.17g", dec$random), collapse=","), "\\n")
""",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["Rscript", str(script)],
        capture_output=True,
        text=True,
        check=True,
    )
    lines = completed.stdout.strip().splitlines()
    return [
        np.asarray(
            [np.nan if value.strip() in ("NA", "NaN") else float(value.strip())
             for value in line.split(",")],
            dtype=np.float64,
        )
        for line in lines[:3]
    ]


def _additive_series():
    t = np.arange(48, dtype=np.float64)
    return 10.0 + 0.3 * t + 2.0 * np.sin(2.0 * np.pi * t / 12.0) + 0.4 * np.cos(
        2.0 * np.pi * t / 12.0
    )


def _multiplicative_series():
    t = np.arange(36, dtype=np.float64)
    return (5.0 + 0.2 * t) * (1.0 + 0.1 * np.sin(2.0 * np.pi * t / 12.0))


def test_seasonal_decompose_matches_r_additive(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    values = _additive_series()
    form, info = _run(values, 12, "additive")
    trend, seasonal, resid = _r_decompose(values, 12, "additive", tmp_path)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 0], values, rtol=0, atol=1e-5)
    np.testing.assert_allclose(data[:, 1], trend, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 2], seasonal, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 3], resid, rtol=0, atol=1e-4, equal_nan=True)
    assert abs(float(np.sum(data[:, 2]))) < 1e-2
    assert info == {"period": 12, "model": "additive", "two_sided": True, "n": 48}


def test_seasonal_decompose_matches_r_multiplicative(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    values = _multiplicative_series()
    form, info = _run(values, 12, "multiplicative")
    trend, seasonal, resid = _r_decompose(values, 12, "multiplicative", tmp_path)
    data = form.data.astype(np.float64)
    np.testing.assert_allclose(data[:, 1], trend, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 2], seasonal, rtol=0, atol=1e-4, equal_nan=True)
    np.testing.assert_allclose(data[:, 3], resid, rtol=0, atol=1e-4, equal_nan=True)
    assert abs(float(np.mean(data[:, 2])) - 1.0) < 1e-3
    assert info["model"] == "multiplicative"
