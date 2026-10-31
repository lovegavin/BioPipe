"""R oracle checks for 0.85 AFT and Hardy-Weinberg operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.aft import AftStep
from src.task.step.steps.hardy_weinberg import HardyWeinbergStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


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


def _aft_data():
    rng = np.random.default_rng(20261112)
    n = 90
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    time = np.exp(1.0 + 0.4 * x1 - 0.3 * x2) * (
        -np.log(rng.random(n))
    ) ** (1.0 / 1.4)
    event = (time <= 3.0).astype(int)
    return pd.DataFrame({"time": time, "event": event, "x1": x1, "x2": x2})


def _aft_form(frame):
    return Form(
        data=frame[["time", "event", "x1", "x2"]].to_numpy(dtype=float),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(len(frame))},
            "feature": {name: i for i, name in enumerate(["time", "event", "x1", "x2"])},
        },
    )


def _hwe_form(rows):
    data = np.asarray(rows, dtype=float)
    return Form(
        data=data,
        dims=["variant", "feature"],
        labels={
            "variant": {f"v{i}": i for i in range(len(rows))},
            "feature": {name: i for i, name in enumerate(["AA", "AB", "BB"])},
        },
    )


def test_aft_matches_r_survreg(tmp_path):
    _require_r_package("survival")
    frame = _aft_data()
    frame.to_csv(tmp_path / "aft.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(survival))
d <- read.csv("{tmp_path.as_posix()}/aft.csv")
f <- survreg(Surv(time, event) ~ x1 + x2, data=d, dist="weibull")
s <- summary(f)
write.csv(data.frame(term=rownames(s$table), coef=s$table[,1], se=s$table[,2],
                     scale=f$scale, loglik=as.numeric(logLik(f))),
          "{tmp_path.as_posix()}/aft_ref.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "aft_ref.csv")

    step = AftStep()
    ctx = Ctx(
        {
            "time_label": "time",
            "event_label": "event",
            "covariates": ["x1", "x2"],
            "output": "fit",
        }
    )
    step.run(ctx, [_aft_form(frame)])
    export = step.export(ctx)
    for i, term in enumerate(["Intercept", "x1", "x2"]):
        row = reference[reference["term"] == ("(Intercept)" if term == "Intercept" else term)].iloc[0]
        assert export["coef"][i] == pytest.approx(float(row["coef"]), abs=2e-5)
        assert export["se"][i] == pytest.approx(float(row["se"]), abs=2e-5)
    scale = float(reference["scale"].iloc[0])
    assert export["scale"] == pytest.approx(scale, abs=2e-5)
    assert export["shape"] == pytest.approx(1.0 / scale, abs=2e-5)
    assert export["loglik"] == pytest.approx(float(reference["loglik"].iloc[0]), abs=2e-5)


def test_hwe_matches_r_hardyweinberg(tmp_path):
    _require_r_package("HardyWeinberg")
    rows = [
        (30, 20, 10),
        (40, 5, 35),
        (35, 30, 35),
        (10, 10, 80),
        (0, 20, 0),
        (50, 0, 50),
    ]
    pd.DataFrame(rows, columns=["AA", "AB", "BB"]).to_csv(tmp_path / "hwe.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(HardyWeinberg))
d <- read.csv("{tmp_path.as_posix()}/hwe.csv")
p <- c()
for (i in seq_len(nrow(d))) {{
  x <- c(d$AA[i], d$AB[i], d$BB[i])
  p[i] <- HWExact(x, verbose=FALSE, pvaluetype="selome")[["pval"]]
}}
write.csv(data.frame(exact_p=p), "{tmp_path.as_posix()}/hwe_ref.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "hwe_ref.csv")

    step = HardyWeinbergStep()
    ctx = Ctx({"output": "hwe"})
    step.run(ctx, [_hwe_form(rows)])
    export = step.export(ctx)
    assert export["exact_p"] == pytest.approx(
        reference["exact_p"].to_numpy(dtype=float), rel=2e-10, abs=1e-14
    )
