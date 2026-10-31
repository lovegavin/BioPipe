"""R oracle checks for 0.79 meta-regression."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.meta_regression import MetaRegressionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _fixture():
    rng = np.random.default_rng(20261109)
    n = 24
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    variance = rng.uniform(0.03, 0.12, size=n)
    effect = (
        0.3
        + 0.5 * x1
        - 0.2 * x2
        + rng.normal(scale=0.8, size=n)
        + rng.normal(scale=np.sqrt(variance))
    )
    return np.column_stack([effect, variance, x1, x2])


def _form(data):
    data = np.asarray(data, dtype=float)
    form = Form(
        data=data,
        dims=["study", "feature"],
        labels={
            "study": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {name: i for i, name in enumerate(["yi", "vi", "x1", "x2"])},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(method):
    step = MetaRegressionStep()
    ctx = Ctx(
        {
            "effect_label": "yi",
            "variance_label": "vi",
            "moderators": ["x1", "x2"],
            "method": method,
            "output": "meta",
        }
    )
    step.run(ctx, [_form(_fixture())])
    return step.export(ctx)


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


def test_meta_regression_matches_r_metafor(tmp_path):
    _require_r_package("metafor")
    data = _fixture()
    pd.DataFrame(data, columns=["yi", "vi", "x1", "x2"]).to_csv(
        tmp_path / "meta.csv", index=False
    )
    script = f"""
suppressPackageStartupMessages(library(metafor))
base <- "{tmp_path.as_posix()}"
d <- read.csv(file.path(base, "meta.csv"))
rows <- list()
for (method in c("FE","DL")) {{
  f <- rma(yi, vi, mods=~x1+x2, data=d, method=method)
  s <- coef(summary(f))
  rows[[method]] <- data.frame(
    method=method,
    term=rownames(s),
    coef=s[,1], se=s[,2], z=s[,3], p=s[,4],
    tau2=as.numeric(f[["tau2"]]),
    Q=as.numeric(f[["QE"]]),
    Qp=as.numeric(f[["QEp"]]),
    I2=as.numeric(f[["I2"]])
  )
}}
write.csv(do.call(rbind, rows), file.path(base, "meta_ref.csv"), row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "meta_ref.csv")
    reference["term"] = reference["term"].replace({"intrcpt": "Intercept"})

    for method, r_method in (("fixed", "FE"), ("random", "DL")):
        export = _run(method)
        rows = reference[reference["method"] == r_method]
        for i, term in enumerate(["Intercept", "x1", "x2"]):
            row = rows[rows["term"] == term].iloc[0]
            assert export["coef"][i] == pytest.approx(float(row["coef"]), abs=2e-6)
            assert export["se"][i] == pytest.approx(float(row["se"]), abs=2e-6)
            assert export["z"][i] == pytest.approx(float(row["z"]), abs=2e-6)
            assert export["p"][i] == pytest.approx(float(row["p"]), abs=2e-8)
        assert export["tau2"] == pytest.approx(float(rows["tau2"].iloc[0]), abs=1e-9)
        assert export["Q"] == pytest.approx(float(rows["Q"].iloc[0]), abs=1e-8)
        assert export["I2"] == pytest.approx(float(rows["I2"].iloc[0]), abs=1e-8)
