"""R-backed oracles for the 0.19 normalization/clinical operators.

These tests deliberately use small hand-sized inputs so the R result can be
read and checked, not merely trusted.  They skip when Rscript or the relevant
Bioconductor package is unavailable.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.cumulative_incidence import CumulativeIncidenceStep
from src.task.step.steps.mantel_haenszel import MantelHaenszelStep
from src.task.step.steps.remove_batch_effect import RemoveBatchEffectStep
from src.task.step.steps.tmm_normalize import TmmNormalizeStep
from src.task.step.steps.tost_equivalence import TostEquivalenceStep
from src.task.step.steps.cochran_armitage import CochranArmitageStep

RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _run_r(tmp_path, script: str) -> None:
    path = tmp_path / "oracle.R"
    path.write_text(script, encoding="utf-8")
    proc = subprocess.run(
        [RSCRIPT, "--no-save", "--no-restore", str(path)],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=180,
    )
    if proc.returncode != 0:
        pytest.fail(
            "R oracle failed\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )


def _installed_r_packages() -> frozenset[str]:
    proc = subprocess.run(
        [RSCRIPT, "--no-save", "--no-restore", "-e",
         "cat(rownames(installed.packages()), sep='\\n')"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        return frozenset()
    return frozenset(line.strip() for line in proc.stdout.splitlines() if line.strip())


def _requires_r(*packages: str):
    if RSCRIPT is None:
        return pytest.mark.skipif(True, reason="Rscript not found")
    missing = sorted(p for p in packages if p not in _installed_r_packages())
    return pytest.mark.skipif(bool(missing), reason=f"R package(s) not installed: {missing}")


@_requires_r("edgeR")
def test_tmm_matches_edger_calc_norm_factors(tmp_path):
    counts = np.array([
        [100, 200, 300],
        [200, 400, 600],
        [300, 100, 200],
        [50, 60, 70],
    ], dtype=np.float32)
    form = _form(counts, ["feature", "sample"],
                 {"feature": _labels([f"g{i}" for i in range(4)]),
                  "sample": _labels([f"s{i}" for i in range(3)])})
    _, info = _run(TmmNormalizeStep(), {}, [form])
    _run_r(
        tmp_path,
        "suppressPackageStartupMessages(library(edgeR))\n"
        "x <- matrix(c(100,200,300,50, 200,400,100,60, 300,600,200,70), nrow=4)\n"
        "f <- calcNormFactors(x)\n"
        "write.csv(data.frame(sample=c('s0','s1','s2'), factor=as.numeric(f)), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    observed = np.array([info["norm_factors"][f"s{i}"] for i in range(3)])
    assert observed == pytest.approx(expected["factor"].to_numpy(), rel=1e-5, abs=1e-7)


@_requires_r("limma")
def test_remove_batch_effect_matches_limma(tmp_path):
    data = np.array([
        [1, 2, 3, 11, 12, 13],
        [2, 4, 6, 12, 14, 16],
        [5, 5, 5, 15, 15, 15],
    ], dtype=np.float32)
    expr = _form(data, ["feature", "sample"],
                 {"feature": _labels(["f0", "f1", "f2"]),
                  "sample": _labels([f"s{i}" for i in range(6)])})
    meta = _form(np.array([[0], [0], [0], [1], [1], [1]], dtype=np.float32),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(6)]),
                  "feature": {"batch": 0}})
    out, _ = _run(RemoveBatchEffectStep(), {"batch_label": "batch"}, [expr, meta])
    _run_r(
        tmp_path,
        "suppressPackageStartupMessages(library(limma))\n"
        "x <- matrix(c(1,2,3,11,12,13, 2,4,6,12,14,16, 5,5,5,15,15,15), nrow=3, byrow=TRUE)\n"
        "b <- factor(c(0,0,0,1,1,1))\n"
        "y <- removeBatchEffect(x, batch=b)\n"
        "write.csv(y, 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv").to_numpy()
    assert out.data == pytest.approx(expected, rel=1e-5, abs=1e-6)


@_requires_r()
def test_mantel_haenszel_matches_r_two_strata(tmp_path):
    table = np.array([[10, 20, 30, 40], [20, 10, 10, 20]], dtype=np.float32)
    form = _form(table, ["stratum", "feature"],
                 {"stratum": {"one": 0, "two": 1},
                  "feature": _labels(["case_exposed", "case_unexposed",
                                      "control_exposed", "control_unexposed"])})
    out, info = _run(MantelHaenszelStep(), {}, [form])
    _run_r(
        tmp_path,
        "a <- array(c(10,20,30,40, 20,10,10,20), dim=c(2,2,2))\n"
        "r <- mantelhaen.test(a, correct=FALSE)\n"
        "write.csv(data.frame(stat=as.numeric(r$statistic), p=r$p.value,\n"
        "  or=as.numeric(r$estimate), lo=r$conf.int[1], hi=r$conf.int[2]),\n"
        "  'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv").iloc[0]
    assert info["mh_statistic"] == pytest.approx(expected["stat"], rel=1e-5, abs=1e-6)
    assert info["p"] == pytest.approx(expected["p"], rel=1e-5, abs=1e-8)
    assert info["odds_ratio"] == pytest.approx(expected["or"], rel=1e-5, abs=1e-6)
    assert info["ci_low"] == pytest.approx(expected["lo"], rel=1e-5, abs=1e-6)
    assert info["ci_high"] == pytest.approx(expected["hi"], rel=1e-5, abs=1e-6)


@_requires_r()
def test_cochran_armitage_matches_r_prop_trend_test(tmp_path):
    table = np.array([[10, 100], [20, 100], [30, 100]], dtype=np.float32)
    form = _form(table, ["group", "feature"],
                 {"group": _labels(["g0", "g1", "g2"]),
                  "feature": {"cases": 0, "total": 1}})
    out, info = _run(CochranArmitageStep(), {}, [form])
    _run_r(
        tmp_path,
        "r <- prop.trend.test(c(10,20,30), c(100,100,100))\n"
        "write.csv(data.frame(stat=as.numeric(r$statistic), p=r$p.value),\n"
        "  'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv").iloc[0]
    assert info["statistic"] == pytest.approx(expected["stat"], rel=1e-5, abs=1e-6)
    assert info["p"] == pytest.approx(expected["p"], rel=1e-5, abs=1e-8)


@_requires_r()
def test_tost_matches_welch_formula(tmp_path):
    # Two features, four samples per group.  The first feature has a true
    # difference of 1; the second is a shifted copy and is not equivalent.
    expr = _form(np.array([
        [10, 10.5, 11, 11.5, 9, 9.5, 10, 10.5],
        [10, 10, 10, 10, 20, 20, 20, 20],
    ], dtype=np.float32), ["feature", "sample"],
        {"feature": _labels(["f0", "f1"]),
         "sample": _labels([f"s{i}" for i in range(8)])})
    meta = _form(np.array([[0], [0], [0], [0], [1], [1], [1], [1]], dtype=np.float32),
                 ["sample", "feature"],
                 {"sample": _labels([f"s{i}" for i in range(8)]),
                  "feature": {"group": 0}})
    out, info = _run(TostEquivalenceStep(), {
        "group_label": "group", "group_a": "0", "group_b": "1", "margin": 2.0,
    }, [expr, meta])
    _run_r(
        tmp_path,
        "a <- c(10,10.5,11,11.5); b <- c(9,9.5,10,10.5)\n"
        "d <- mean(a)-mean(b); se <- sqrt(var(a)/4+var(b)/4); df <- 6\n"
        "lo <- d - qt(.95, df)*se; hi <- d + qt(.95, df)*se\n"
        "pl <- pt((d+2)/se, df, lower.tail=FALSE)\n"
        "ph <- pt((d-2)/se, df, lower.tail=TRUE)\n"
        "write.csv(data.frame(diff=d, se=se, df=df, p_low=pl, p_high=ph,\n"
        "  p=max(pl,ph), ci_low=lo, ci_high=hi), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv").iloc[0]
    col = out.labels["statistic"]
    row = 0
    for name in ("diff", "se", "df", "p_low", "p_high", "p", "ci_low", "ci_high"):
        assert out.data[row, col[name]] == pytest.approx(expected[name], rel=1e-5, abs=1e-7)


@_requires_r("survival")
def test_cumulative_incidence_matches_survfit(tmp_path):
    clinical = _form(np.array([
        [1, 1], [2, 2], [3, 0], [4, 1], [5, 0], [6, 2],
    ], dtype=np.float32), ["sample", "feature"],
        {"sample": _labels([f"s{i}" for i in range(6)]),
         "feature": {"time": 0, "event": 1}})
    out, _ = _run(CumulativeIncidenceStep(), {
        "time_label": "time", "event_label": "event",
    }, [clinical])
    _run_r(
        tmp_path,
        "suppressPackageStartupMessages(library(survival))\n"
        "t <- c(1,2,3,4,5,6); e <- c(1,2,0,1,0,2)\n"
        "fit <- survfit(Surv(t, factor(e)) ~ 1)\n"
        "s <- summary(fit, times=c(0,1,2,4,6))\n"
        "write.csv(data.frame(time=s$time, cif=s$pstate[,2]), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    time_index = out.labels["time"]
    group_index = out.labels["group"]["all"]
    for _, row in expected.iterrows():
        assert out.data[time_index[str(int(row["time"]))], group_index] == pytest.approx(
            row["cif"], rel=1e-5, abs=1e-7
        )
