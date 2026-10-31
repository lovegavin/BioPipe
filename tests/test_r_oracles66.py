"""R oracle checks for 0.83 db-RDA and leave-one-out meta-analysis."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.dbrda import DbrdaStep
from src.task.step.steps.leave_one_out import LeaveOneOutStep

Y = np.array(
    [
        [10, 20, 30],
        [20, 40, 20],
        [30, 10, 10],
        [15, 25, 35],
        [25, 15, 20],
        [5, 30, 25],
        [20, 20, 40],
        [30, 20, 10],
    ],
    dtype=float,
)
X = np.column_stack(
    [
        [-1, -0.5, 0, 0.5, 1, -1, 0, 1],
        [0, 1, 0, 1, 0, 1, 1, 0],
    ]
)
EFFECT = np.array(
    [0.4629, 0.6535, 0.4254, 0.3927, 0.4661, -0.6996, -0.3884, 1.0418]
)
VARIANCE = np.array(
    [0.1281, 0.1528, 0.0869, 0.0809, 0.2528, 0.1163, 0.1557, 0.1949]
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _form(values, dims, labels):
    form = Form(
        data=np.asarray(values, dtype=float),
        dims=dims,
        labels=labels,
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _require_r_package(package: str) -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", f'cat(requireNamespace("{package}", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip(f"R {package} is not available")


def test_dbrda_matches_r_vegan(tmp_path):
    _require_r_package("vegan")
    pd.DataFrame(Y, index=[f"s{i}" for i in range(8)]).to_csv(tmp_path / "y.csv")
    pd.DataFrame(X, index=[f"s{i}" for i in range(8)], columns=["x1", "x2"]).to_csv(
        tmp_path / "x.csv"
    )
    script = f"""
suppressPackageStartupMessages(library(vegan))
Y <- as.matrix(read.csv("{tmp_path.as_posix()}/y.csv", row.names=1, check.names=FALSE))
X <- read.csv("{tmp_path.as_posix()}/x.csv", row.names=1, check.names=FALSE)
f <- dbrda(vegdist(Y, method="bray") ~ x1 + x2, data=X)
write.csv(data.frame(eig=as.numeric(f$CCA$eig)),
          file="{tmp_path.as_posix()}/eig.csv", row.names=FALSE)
write.csv(data.frame(total=f$tot.chi, constrained=f$CCA$tot.chi,
                     unconstrained=f$CA$tot.chi),
          file="{tmp_path.as_posix()}/inertia.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    eig = pd.read_csv(tmp_path / "eig.csv")["eig"].to_numpy()
    inertia = pd.read_csv(tmp_path / "inertia.csv").iloc[0]
    export = _run(
        DbrdaStep(),
        {"n_components": 2, "output": "d"},
        [
            _form(
                Y,
                ["sample", "feature"],
                {
                    "sample": {f"s{i}": i for i in range(8)},
                    "feature": {"sp1": 0, "sp2": 1, "sp3": 2},
                },
            ),
            _form(
                X,
                ["sample", "predictor"],
                {
                    "sample": {f"s{i}": i for i in range(8)},
                    "predictor": {"x1": 0, "x2": 1},
                },
            ),
        ],
    )
    np.testing.assert_allclose(export["eigenvalues"], eig, rtol=0, atol=1e-10)
    assert export["total_inertia"] == pytest.approx(float(inertia["total"]), abs=1e-10)
    assert export["constrained_inertia"] == pytest.approx(
        float(inertia["constrained"]), abs=1e-10
    )
    assert export["unconstrained_inertia"] == pytest.approx(
        float(inertia["unconstrained"]), abs=1e-10
    )


def test_leave_one_out_matches_r_metafor(tmp_path):
    _require_r_package("metafor")
    pd.DataFrame({"yi": EFFECT, "vi": VARIANCE}).to_csv(tmp_path / "data.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(metafor))
d <- read.csv("{tmp_path.as_posix()}/data.csv")
for (m in c("FE", "DL")) {{
  l <- leave1out(rma(d$yi, d$vi, method=m))
  tau2 <- if (m == "DL") l[["tau2"]] else rep(0, length(l[["estimate"]]))
  out <- file.path("{tmp_path.as_posix()}", paste0("loo_", m, ".csv"))
  write.csv(data.frame(estimate=l[["estimate"]], se=l[["se"]],
                       tau2=tau2, I2=l[["I2"]], Q=l[["Q"]], Qp=l[["Qp"]]),
            file=out, row.names=FALSE)
}}
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    form = _form(
        np.column_stack([EFFECT, VARIANCE]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(8)},
            "feature": {"yi": 0, "vi": 1},
        },
    )
    for method, r_method in [("fixed", "FE"), ("random", "DL")]:
        expected = pd.read_csv(tmp_path / f"loo_{r_method}.csv")
        export = _run(
            LeaveOneOutStep(),
            {
                "study_dim": "sample",
                "effect_label": "yi",
                "variance_label": "vi",
                "method": method,
                "output": "loo",
            },
            [form],
        )
        for column, key in [
            ("estimate", "estimate"),
            ("se", "se"),
            ("tau2", "tau2"),
            ("I2", "I2"),
            ("Q", "Q"),
            ("Qp", "Qp"),
        ]:
            np.testing.assert_allclose(
                [row[key] for row in export["results"]],
                expected[column].to_numpy(),
                rtol=0,
                atol=1e-10,
            )
