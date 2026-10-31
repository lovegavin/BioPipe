"""R oracle checks for 0.81 inverse Gaussian, betadisper, and ZINB."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.betadisper import BetadisperStep
from src.task.step.steps.inverse_gaussian_regression import (
    InverseGaussianRegressionStep,
)
from src.task.step.steps.zero_inflated_negative_binomial import (
    ZeroInflatedNegativeBinomialStep,
)


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


def _form(values, names):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {name: i for i, name in enumerate(names)},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _ig_data():
    rng = np.random.default_rng(20261110)
    n = 60
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    mu = np.exp(0.4 + 0.4 * x1 - 0.3 * x2)
    y = rng.gamma(shape=2.0, scale=mu / 2.0)
    return np.column_stack([y, x1, x2])


def _zinb_data():
    from scipy.special import expit

    rng = np.random.default_rng(20261111)
    n = 220
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    z1 = rng.normal(size=n)
    mu = np.exp(0.5 + 0.4 * x1 - 0.3 * x2)
    theta = 1.25
    y_nb = rng.negative_binomial(theta, theta / (theta + mu))
    zero = expit(-0.8 + 0.6 * z1)
    y = np.where(rng.random(n) < zero, 0, y_nb).astype(int)
    return np.column_stack([y, x1, x2, z1])


def _betadisper_data():
    a = np.array([[0, 0], [0, 1], [1, 0], [1, 1], [0.5, 0.5], [0.2, 0.8]])
    b = np.array([[3, 0], [5, 1], [6, 0], [7, 1], [4.5, 1.5], [3.5, -1.0]])
    xy = np.vstack([a, b])
    d = np.sqrt(((xy[:, None, :] - xy[None, :, :]) ** 2).sum(axis=2))
    groups = np.array(["A"] * 6 + ["B"] * 6)
    return d, groups


def test_inverse_gaussian_matches_r_glm(tmp_path):
    _require_r_package("stats")
    data = _ig_data()
    pd.DataFrame(data, columns=["y", "x1", "x2"]).to_csv(
        tmp_path / "ig.csv", index=False
    )
    script = f"""
d <- read.csv("{tmp_path.as_posix()}/ig.csv")
f <- glm(y ~ x1 + x2, data=d, family=inverse.gaussian(link="log"))
s <- coef(summary(f))
write.csv(data.frame(term=rownames(s), coef=s[,1], se=s[,2]),
          file="{tmp_path.as_posix()}/ig_ref.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "ig_ref.csv")
    export = _run(
        InverseGaussianRegressionStep(),
        {"response_label": "y", "predictors": ["x1", "x2"], "output": "ig"},
        [_form(data, ["y", "x1", "x2"])],
    )
    for i, term in enumerate(["(Intercept)", "x1", "x2"]):
        row = reference[reference["term"] == term].iloc[0]
        assert export["coef"][i] == pytest.approx(float(row["coef"]), abs=3e-5)
        assert export["se"][i] == pytest.approx(float(row["se"]), abs=3e-6)


def test_betadisper_matches_r_vegan(tmp_path):
    _require_r_package("vegan")
    d, groups = _betadisper_data()
    pd.DataFrame(d).to_csv(tmp_path / "d.csv", index=False, header=False)
    pd.DataFrame({"group": groups}).to_csv(tmp_path / "g.csv", index=False)
    script = f"""
suppressPackageStartupMessages(library(vegan))
d <- as.matrix(read.csv("{tmp_path.as_posix()}/d.csv", header=FALSE))
g <- read.csv("{tmp_path.as_posix()}/g.csv")[["group"]]
b <- betadisper(as.dist(d), g, type="centroid")
a <- anova(b)
write.csv(data.frame(distance=b[["distances"]]),
          file="{tmp_path.as_posix()}/dist_ref.csv", row.names=FALSE)
write.csv(data.frame(group=names(b[["group.distances"]]),
                     mean=as.numeric(b[["group.distances"]])),
          file="{tmp_path.as_posix()}/means_ref.csv", row.names=FALSE)
write.csv(data.frame(F=a[1,4], p=a[1,5]),
          file="{tmp_path.as_posix()}/anova_ref.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    distances = pd.read_csv(tmp_path / "dist_ref.csv")["distance"].to_numpy()
    means = pd.read_csv(tmp_path / "means_ref.csv")["mean"].to_numpy()
    anova = pd.read_csv(tmp_path / "anova_ref.csv").iloc[0]

    dist_form = Form(
        data=d,
        dims=["sample", "sample_b"],
        labels={
            "sample": {f"s{i}": i for i in range(len(d))},
            "sample_b": {f"s{i}": i for i in range(len(d))},
        },
        info={"missing_code": np.nan},
    )
    meta_form = Form(
        data=groups.reshape(-1, 1),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(len(groups))},
            "feature": {"group": 0},
        },
        info={"missing_code": np.nan},
    )
    export = _run(
        BetadisperStep(),
        {"group_label": "group", "output": "bd"},
        [dist_form, meta_form],
    )
    np.testing.assert_allclose(export["distances"], distances, rtol=0, atol=1e-12)
    np.testing.assert_allclose(
        list(export["group_means"].values()), means, rtol=0, atol=1e-12
    )
    assert export["F"] == pytest.approx(float(anova["F"]), abs=1e-10)
    assert export["p"] == pytest.approx(float(anova["p"]), abs=1e-14)


def test_zinb_matches_r_pscl(tmp_path):
    _require_r_package("pscl")
    data = _zinb_data()
    pd.DataFrame(data, columns=["y", "x1", "x2", "z1"]).to_csv(
        tmp_path / "zinb.csv", index=False
    )
    script = f"""
suppressPackageStartupMessages(library(pscl))
d <- read.csv("{tmp_path.as_posix()}/zinb.csv")
f <- zeroinfl(y ~ x1 + x2 | z1, data=d, dist="negbin")
s <- summary(f)$coefficients
count <- s$count
zero <- s$zero
write.csv(data.frame(component=c(rep("count", nrow(count)), rep("zero", nrow(zero))),
                     term=c(rownames(count), rownames(zero)),
                     coef=c(count[,1], zero[,1]),
                     se=c(count[,2], zero[,2])),
          file="{tmp_path.as_posix()}/zinb_ref.csv", row.names=FALSE)
writeLines(c(sprintf("%.17g", f$theta), sprintf("%.17g", as.numeric(logLik(f)))),
           "{tmp_path.as_posix()}/zinb_extra.txt")
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    reference = pd.read_csv(tmp_path / "zinb_ref.csv")
    extra = (tmp_path / "zinb_extra.txt").read_text().splitlines()
    export = _run(
        ZeroInflatedNegativeBinomialStep(),
        {
            "response_label": "y",
            "count_predictors": ["x1", "x2"],
            "zero_predictors": ["z1"],
            "output": "zinb",
        },
        [_form(data, ["y", "x1", "x2", "z1"])],
    )
    for i, term in enumerate(["(Intercept)", "x1", "x2"]):
        row = reference[(reference["component"] == "count") & (reference["term"] == term)].iloc[0]
        assert export["count_coef"][i] == pytest.approx(float(row["coef"]), abs=3e-5)
    for i, term in enumerate(["(Intercept)", "z1"]):
        row = reference[(reference["component"] == "zero") & (reference["term"] == term)].iloc[0]
        assert export["zero_coef"][i] == pytest.approx(float(row["coef"]), abs=3e-5)
    assert export["theta"] == pytest.approx(float(extra[0]), abs=1e-4)
    assert export["loglike"] == pytest.approx(float(extra[1]), abs=1e-7)
