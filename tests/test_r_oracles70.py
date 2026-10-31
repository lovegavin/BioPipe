"""R oracle checks for 0.88 decision curve analysis and LOWESS."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.dca import DcaStep
from src.task.step.steps.lowess import LowessStep


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


def _require_r() -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")


Y = np.array([0.0, 0.0, 0.0, 0.0, 1.0, 1.0, 1.0, 1.0])
P = np.array([0.05, 0.15, 0.25, 0.35, 0.65, 0.75, 0.85, 0.95])
THRESHOLDS = [0.1, 0.2, 0.5, 0.8]


def test_dca_matches_r_dcurves(tmp_path):
    _require_r()
    probe = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("dcurves", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if probe.stdout.strip() != "TRUE":
        pytest.skip("R package dcurves is not available")

    pd.DataFrame({"y": Y, "p": P}).to_csv(tmp_path / "dca.csv", index=False)
    script = f"""
    library(dcurves)
    d <- read.csv("{tmp_path / 'dca.csv'}")
    x <- dca(y ~ p, data=d, thresholds=c({','.join(str(v) for v in THRESHOLDS)}))
    tab <- x[["dca"]]
    model <- tab[tab$variable == "p", ]
    all <- tab[tab$variable == "all", ]
    none <- tab[tab$variable == "none", ]
    model <- model[order(model$threshold), ]
    all <- all[order(all$threshold), ]
    none <- none[order(none$threshold), ]
    out <- data.frame(
        threshold=model$threshold,
        net_benefit=model$net_benefit,
        treat_all=all$net_benefit,
        treat_none=none$net_benefit,
        true_positive=model$tp_rate * model$n,
        false_positive=model$fp_rate * model$n
    )
    write.csv(out, "{tmp_path / 'dca_ref.csv'}", row.names=FALSE)
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    export, out = _run(
        DcaStep(),
        {
            "outcome_label": "y",
            "probability_label": "p",
            "thresholds": THRESHOLDS,
            "output": "curve",
        },
        _form(np.column_stack([Y, P]), ("y", "p")),
    )
    ref = pd.read_csv(tmp_path / "dca_ref.csv")
    np.testing.assert_allclose(ref["threshold"].to_numpy(), export["thresholds"], atol=1e-12)
    np.testing.assert_allclose(out.data[:, 1], ref["net_benefit"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.data[:, 2], ref["treat_all"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.data[:, 3], ref["treat_none"], rtol=0, atol=1e-12)
    np.testing.assert_allclose(out.data[:, 4], ref["true_positive"], atol=1e-12)
    np.testing.assert_allclose(out.data[:, 5], ref["false_positive"], atol=1e-12)


X = np.arange(1.0, 21.0)
Y_LOW = np.sin(X / 3.0) + 0.1 * X


def test_lowess_matches_r_stats_lowess(tmp_path):
    _require_r()
    pd.DataFrame({"x": X, "y": Y_LOW}).to_csv(tmp_path / "lowess.csv", index=False)
    script = f"""
    d <- read.csv("{tmp_path / 'lowess.csv'}")
    z <- stats::lowess(d$x, d$y, f=2/3, iter=3)
    write.csv(data.frame(x=z$x, fitted=z$y), "{tmp_path / 'lowess_ref.csv'}",
              row.names=FALSE)
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)

    export, out = _run(
        LowessStep(),
        {"x_label": "x", "y_label": "y", "frac": 2.0 / 3.0, "iterations": 3, "output": "smooth"},
        _form(np.column_stack([X, Y_LOW]), ("x", "y")),
    )
    ref = pd.read_csv(tmp_path / "lowess_ref.csv")
    np.testing.assert_allclose(ref["x"].to_numpy(), export["x"], atol=1e-12)
    np.testing.assert_allclose(out.data[:, 2], ref["fitted"], rtol=0, atol=1e-12)
