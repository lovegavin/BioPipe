"""R-backed oracles for the nonparametric operators.

The tests compare hand-sized, tie-controlled datasets with base R (or the
``Kendall`` package).  They are skipped when Rscript is unavailable, so the
Python-only environment remains usable.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.bartlett import BartlettStep
from src.task.step.steps.friedman import FriedmanStep
from src.task.step.steps.ks_2samp import Ks2SampStep
from src.task.step.steps.mann_kendall import MannKendallStep
from src.task.step.steps.wilcoxon import WilcoxonStep

RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels, dtype=np.float32):
    form = Form(np.asarray(data, dtype=dtype), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


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


def _requires_r(*packages: str):
    if RSCRIPT is None:
        return pytest.mark.skipif(True, reason="Rscript not found")
    missing = sorted(
        p for p in packages
        if p not in _installed_r_packages()
    )
    return pytest.mark.skipif(bool(missing), reason=f"R package(s) not installed: {missing}")


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


def _group_forms(data: np.ndarray, groups: list[str]):
    samples = [f"s{i}" for i in range(len(groups))]
    values = _form(
        data,
        ["feature", "sample"],
        {
            "feature": {f"f{i}": i for i in range(data.shape[0])},
            "sample": {s: i for i, s in enumerate(samples)},
        },
    )
    meta = _form(
        np.asarray(groups, dtype=object).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {s: i for i, s in enumerate(samples)}, "feature": {"group": 0}},
        dtype=object,
    )
    return values, meta


def _write_wide(tmp_path, data: np.ndarray, groups: list[str]) -> None:
    samples = [f"s{i}" for i in range(data.shape[1])]
    pd.DataFrame(
        data,
        index=[f"f{i}" for i in range(data.shape[0])],
        columns=samples,
    ).to_csv(tmp_path / "values.csv")
    pd.DataFrame({"group": groups}).to_csv(tmp_path / "meta.csv", index=False)


@_requires_r()
def test_paired_wilcoxon_matches_r_wilcox_test(tmp_path):
    data = np.array(
        [
            [1.1, 2.4, 2.9, 4.8, 6.1, 7.9, 9.2, 10.4],
            [2.0, 2.2, 3.1, 4.1, 5.9, 8.4, 9.0, 11.1],
        ],
        dtype=float,
    )
    groups = ["a"] * 4 + ["b"] * 4
    values, meta = _group_forms(data, groups)
    out, _ = _run(WilcoxonStep(), {"group_label": "group"}, [values, meta])
    _write_wide(tmp_path, data, groups)
    _run_r(
        tmp_path,
        "x <- as.matrix(read.csv('values.csv', row.names=1, check.names=FALSE))\n"
        "g <- read.csv('meta.csv')$group\n"
        "rows <- lapply(seq_len(nrow(x)), function(i) {\n"
        "  r <- wilcox.test(as.numeric(x[i, g == 'a']), as.numeric(x[i, g == 'b']), paired=TRUE, exact=TRUE)\n"
        "  data.frame(W=as.numeric(r$statistic), P=r$p.value)\n"
        "})\n"
        "write.csv(do.call(rbind, rows), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    assert out.data[:, 0] == pytest.approx(expected["W"].to_numpy(), rel=1e-6, abs=1e-6)
    assert out.data[:, 1] == pytest.approx(expected["P"].to_numpy(), rel=1e-5, abs=1e-7)


@_requires_r()
def test_friedman_matches_r_friedman_test(tmp_path):
    data = np.array(
        [[1.0, 2.1, 2.2, 4.3, 4.4, 6.2, 1.4, 2.2, 3.1, 4.0, 5.3, 6.8, 1.9, 2.8, 3.4, 4.7, 5.8, 7.1]],
        dtype=float,
    )
    groups = ["g0"] * 6 + ["g1"] * 6 + ["g2"] * 6
    values, meta = _group_forms(data, groups)
    out, _ = _run(FriedmanStep(), {"group_label": "group"}, [values, meta])
    _write_wide(tmp_path, data, groups)
    _run_r(
        tmp_path,
        "x <- as.matrix(read.csv('values.csv', row.names=1, check.names=FALSE))\n"
        "m <- matrix(as.numeric(x), nrow=6, ncol=3)\n"
        "r <- friedman.test(m)\n"
        "write.csv(data.frame(stat=as.numeric(r$statistic), P=r$p.value), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    assert out.data[0, 0] == pytest.approx(expected["stat"].iloc[0], rel=1e-5, abs=1e-5)
    assert out.data[0, 1] == pytest.approx(expected["P"].iloc[0], rel=1e-5, abs=1e-7)


@_requires_r()
def test_bartlett_matches_r_bartlett_test(tmp_path):
    data = np.array(
        [[1.0, 1.3, 1.6, 1.9, 2.2, 2.7, 2.0, 2.5, 3.1, 3.8, 4.4, 5.2, 4.2, 4.4, 4.9, 5.1, 5.8, 6.5]],
        dtype=float,
    )
    groups = ["g0"] * 6 + ["g1"] * 6 + ["g2"] * 6
    values, meta = _group_forms(data, groups)
    out, _ = _run(BartlettStep(), {"group_label": "group"}, [values, meta])
    _write_wide(tmp_path, data, groups)
    _run_r(
        tmp_path,
        "x <- as.matrix(read.csv('values.csv', row.names=1, check.names=FALSE))\n"
        "g <- read.csv('meta.csv')$group\n"
        "r <- bartlett.test(list(as.numeric(x[1, g == 'g0']), as.numeric(x[1, g == 'g1']), as.numeric(x[1, g == 'g2'])))\n"
        "write.csv(data.frame(stat=as.numeric(r$statistic), P=r$p.value), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    assert out.data[0, 0] == pytest.approx(expected["stat"].iloc[0], rel=1e-5, abs=1e-5)
    assert out.data[0, 1] == pytest.approx(expected["P"].iloc[0], rel=1e-5, abs=1e-7)


@_requires_r()
def test_ks_2samp_matches_r_ks_test(tmp_path):
    data = np.array(
        [[0.1, 0.4, 0.7, 1.1, 1.6, 2.0, 2.4, 3.0, 1.0, 1.2, 2.1, 2.2, 2.8, 3.4, 4.1, 4.8]],
        dtype=float,
    )
    groups = ["a"] * 8 + ["b"] * 8
    values, meta = _group_forms(data, groups)
    out, _ = _run(Ks2SampStep(), {"group_label": "group", "method": "exact"}, [values, meta])
    _write_wide(tmp_path, data, groups)
    _run_r(
        tmp_path,
        "x <- as.matrix(read.csv('values.csv', row.names=1, check.names=FALSE))\n"
        "g <- read.csv('meta.csv')$group\n"
        "r <- ks.test(as.numeric(x[1, g == 'a']), as.numeric(x[1, g == 'b']), exact=TRUE)\n"
        "write.csv(data.frame(D=as.numeric(r$statistic), P=r$p.value), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    assert out.data[0, 0] == pytest.approx(expected["D"].iloc[0], rel=1e-6, abs=1e-6)
    assert out.data[0, 1] == pytest.approx(expected["P"].iloc[0], rel=1e-5, abs=1e-7)


@_requires_r("Kendall")
def test_mann_kendall_matches_r_kendall(tmp_path):
    x = np.array([2.0, 3.1, 2.8, 4.2, 4.0, 5.3, 6.1, 5.8, 7.2, 7.0, 8.4, 9.1])
    form = _form(
        x.reshape(-1, 1),
        ["time", "feature"],
        {"time": {f"t{i}": i for i in range(len(x))}, "feature": {"x": 0}},
    )
    out, _ = _run(MannKendallStep(), {}, [form])
    pd.DataFrame({"x": x}).to_csv(tmp_path / "series.csv", index=False)
    _run_r(
        tmp_path,
        "suppressPackageStartupMessages(library(Kendall))\n"
        "x <- read.csv('series.csv')$x\n"
        "r <- MannKendall(x)\n"
        "write.csv(data.frame(S=as.numeric(r$S), tau=as.numeric(r$tau), P=as.numeric(r$sl)), 'reference.csv', row.names=FALSE)\n",
    )
    expected = pd.read_csv(tmp_path / "reference.csv")
    assert out.data[0, 0] == pytest.approx(expected["S"].iloc[0], rel=1e-6, abs=1e-6)
    assert out.data[0, 1] == pytest.approx(expected["tau"].iloc[0], rel=1e-6, abs=1e-6)
    assert out.data[0, 3] == pytest.approx(expected["P"].iloc[0], rel=1e-5, abs=1e-7)
