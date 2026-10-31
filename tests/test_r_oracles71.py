"""R oracle check for 0.89 Bai-Perron breakpoints."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.bai_perron import BaiPerronStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx), ctx[params.get("output", step.name)]


def _form(values, labels):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(labels)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def test_bai_perron_matches_r_strucchange(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("strucchange", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip("R package strucchange is not available")

    n = 120
    i = np.arange(1, n + 1, dtype=float)
    x1 = np.sin(i / 5.0)
    x2 = np.cos(i / 7.0)
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + 0.1 * np.sin(i * 1.7)
    y[40:80] += 2.0
    y[80:] -= 1.0
    pd.DataFrame({"y": y, "x1": x1, "x2": x2}).to_csv(tmp_path / "bp.csv", index=False)

    script = f"""
    suppressPackageStartupMessages(library(strucchange))
    d <- read.csv("{tmp_path / 'bp.csv'}")
    bp <- breakpoints(y ~ x1 + x2, data=d, h=0.15, breaks=2)
    b <- as.integer(bp$breakpoints)
    rss <- bp$RSS(1, b[1]) + bp$RSS(b[1] + 1, b[2]) + bp$RSS(b[2] + 1, nrow(d))
    write.csv(data.frame(breakpoint=b), "{tmp_path / 'breaks.csv'}", row.names=FALSE)
    write.csv(data.frame(rss=rss), "{tmp_path / 'rss.csv'}", row.names=FALSE)
    write.csv(coef(bp), "{tmp_path / 'coef.csv'}", row.names=FALSE)
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    export, out = _run(
        BaiPerronStep(),
        {
            "response_label": "y",
            "predictors": ["x1", "x2"],
            "n_breaks": 2,
            "min_segment": 0.15,
            "output": "segments",
        },
        _form(np.column_stack([y, x1, x2]), ("y", "x1", "x2")),
    )
    ref_breaks = pd.read_csv(tmp_path / "breaks.csv")["breakpoint"].to_numpy()
    ref_rss = float(pd.read_csv(tmp_path / "rss.csv").iloc[0, 0])
    ref_coef = pd.read_csv(tmp_path / "coef.csv").to_numpy(dtype=float)
    assert export["breaks"] == ref_breaks.tolist()
    assert export["rss"] == pytest.approx(ref_rss, abs=1e-6)
    np.testing.assert_allclose(out.data, ref_coef, rtol=0, atol=1e-6)
