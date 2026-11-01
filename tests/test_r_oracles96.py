"""R oracle for the 1.15.0 betadiver, tsallis and varpart operators."""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.betadiver import METHODS, BetadiverStep
from src.task.step.steps.tsallis import TsallisStep
from src.task.step.steps.varpart import VarpartStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

ABUNDANCE = np.asarray([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=np.float64)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"], step.export(ctx)


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float32), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _write_matrix(path: Path, matrix, rows, columns):
    lines = ["," + ",".join(str(name) for name in columns)]
    for name, row in zip(rows, matrix):
        lines.append(",".join([str(name)] + [format(float(value), ".17g") for value in row]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_table(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _number(text):
    return np.nan if text in ("NA", "") else float(text)


R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]
out <- args[2]
suppressPackageStartupMessages(library(vegan))
options(digits = 17)

x <- as.matrix(read.csv(file.path(inp, "comm.csv"), row.names = 1))
methods <- c("w", "-1", "c", "wb", "r", "I", "e", "t", "me", "j", "sor", "m",
             "-2", "co", "cc", "g", "-3", "l", "19", "hk", "rlb", "sim", "gl", "z")
lines <- c("method,i,j,value")
for (m in methods) {
    d <- as.matrix(betadiver(x, method = m))
    for (i in 2:nrow(d)) {
        for (j in 1:(i - 1)) {
            lines <- c(lines, paste(m, i, j, format(d[i, j], digits = 17), sep = ","))
        }
    }
}
writeLines(lines, file.path(out, "betadiver.csv"))

for (v in c("plain", "norm", "hill")) {
    res <- switch(v,
        plain = tsallis(x, scales = c(0, 0.5, 1, 2)),
        norm = tsallis(x, scales = c(0, 0.5, 1, 2), norm = TRUE),
        hill = tsallis(x, scales = c(0, 0.5, 1, 2), hill = TRUE))
    m <- as.matrix(res)
    lines <- c("variant,i,scale,value")
    for (i in 1:nrow(m)) {
        for (j in 1:ncol(m)) {
            lines <- c(lines, paste(v, i, colnames(m)[j],
                                    format(m[i, j], digits = 17), sep = ","))
        }
    }
    writeLines(lines, file.path(out, paste0("tsallis_", v, ".csv")))
}

Y <- as.matrix(read.csv(file.path(inp, "y.csv"), row.names = 1))
X1 <- as.matrix(read.csv(file.path(inp, "x1.csv"), row.names = 1))
X2 <- as.matrix(read.csv(file.path(inp, "x2.csv"), row.names = 1))
vp <- varpart(Y, X1, X2)
ind <- vp$part$indfract
fract <- vp$part$fract
lines <- c("kind,fraction,column,value")
for (r in rownames(ind)) {
    for (cn in c("Df", "R.squared", "Adj.R.squared")) {
        lines <- c(lines, paste("ind", shQuote(r), cn, format(ind[r, cn], digits = 17), sep = ","))
    }
}
for (r in rownames(fract)) {
    for (cn in c("Df", "R.squared", "Adj.R.squared")) {
        lines <- c(lines, paste("fract", shQuote(r), cn, format(fract[r, cn], digits = 17), sep = ","))
    }
}
writeLines(lines, file.path(out, "varpart.csv"))
"""


@pytest.fixture(scope="module")
def oracle(tmp_path_factory):
    root = tmp_path_factory.mktemp("oracle96")
    inp = root / "in"
    out = root / "out"
    inp.mkdir()
    out.mkdir()
    comm_rows = [f"s{i}" for i in range(ABUNDANCE.shape[0])]
    comm_cols = [f"t{i}" for i in range(ABUNDANCE.shape[1])]
    _write_matrix(inp / "comm.csv", ABUNDANCE, comm_rows, comm_cols)
    rng = np.random.default_rng(20261102)
    n = 24
    response = rng.normal(size=(n, 3))
    first = rng.normal(size=(n, 2))
    second = 0.4 * first + rng.normal(size=(n, 2))
    sample_rows = [f"s{i}" for i in range(n)]
    _write_matrix(inp / "y.csv", response, sample_rows, ["y0", "y1", "y2"])
    _write_matrix(inp / "x1.csv", first, sample_rows, ["p0", "p1"])
    _write_matrix(inp / "x2.csv", second, sample_rows, ["q0", "q1"])
    script = root / "oracle.R"
    script.write_text(R_CODE, encoding="utf-8")
    result = subprocess.run([RSCRIPT, str(script), str(inp), str(out)],
                            capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        pytest.fail(f"Rscript failed: {result.stderr}\n{result.stdout}")
    return {"out": out, "response": response, "first": first, "second": second}


def _comm_form():
    samples = {f"s{i}": i for i in range(ABUNDANCE.shape[0])}
    taxa = {f"t{i}": i for i in range(ABUNDANCE.shape[1])}
    return _form(ABUNDANCE, ["sample", "taxon"],
                 {"sample": samples, "taxon": taxa})


def test_betadiver_matches_vegan(oracle):
    rows = _read_table(oracle["out"] / "betadiver.csv")
    expected = {method: np.zeros((ABUNDANCE.shape[0], ABUNDANCE.shape[0]))
                for method in METHODS}
    for row in rows:
        i = int(row["i"]) - 1
        j = int(row["j"]) - 1
        value = _number(row["value"])
        expected[row["method"]][i, j] = value
        expected[row["method"]][j, i] = value
    form = _comm_form()
    for method in METHODS:
        out, _ = _run(BetadiverStep(), (form,), {"method": method})
        np.testing.assert_allclose(out.data, expected[method].astype(np.float32),
                                   rtol=1e-6, atol=1e-7, err_msg=method)


def test_tsallis_matches_vegan(oracle):
    form = _comm_form()
    for variant, params in (("plain", {}), ("norm", {"norm": True}),
                            ("hill", {"hill": True})):
        rows = _read_table(oracle["out"] / f"tsallis_{variant}.csv")
        by_scale = {}
        for row in rows:
            by_scale.setdefault(row["scale"], {})[int(row["i"]) - 1] = _number(row["value"])
        scales = list(by_scale)
        expected = np.column_stack([np.asarray([by_scale[name][i]
                                                for i in range(ABUNDANCE.shape[0])])
                                    for name in scales])
        out, _ = _run(TsallisStep(), (form,),
                      {"scales": [0, 0.5, 1, 2], **params})
        assert list(out.labels["scale"]) == scales
        np.testing.assert_allclose(out.data, expected.astype(np.float32),
                                   rtol=1e-6, atol=1e-6, err_msg=variant)


def test_varpart_matches_vegan(oracle):
    rows = _read_table(oracle["out"] / "varpart.csv")
    ind = {}
    fract = {}
    for row in rows:
        name = row["fraction"].replace(chr(39), "").strip(chr(34))
        target = ind if row["kind"] == "ind" else fract
        target[(name, row["column"])] = _number(row["value"])
    n = 24
    samples = {f"s{i}": i for i in range(n)}
    y = _form(oracle["response"], ["sample", "response"],
              {"sample": samples, "response": {"y0": 0, "y1": 1, "y2": 2}})
    x1 = _form(oracle["first"], ["sample", "predictor"],
               {"sample": samples, "predictor": {"p0": 0, "p1": 1}})
    x2 = _form(oracle["second"], ["sample", "predictor_b"],
               {"sample": samples, "predictor_b": {"q0": 0, "q1": 1}})
    out, export = _run(VarpartStep(), (y, x1, x2), {})
    pairs = {"a": "[a] = X1|X2", "b": "[b] = X2|X1", "c": "[c]", "d": "[d] = Residuals"}
    for key, name in pairs.items():
        assert export[key] == pytest.approx(ind[(name, "Adj.R.squared")], rel=1e-5, abs=1e-7)
    for index, name in enumerate(["[a+c] = X1", "[b+c] = X2", "[a+b+c] = X1+X2"]):
        assert export["adj_r2"][index] == pytest.approx(fract[(name, "Adj.R.squared")], rel=1e-5, abs=1e-7)
        assert export["r2"][index] == pytest.approx(fract[(name, "R.squared")], rel=1e-5, abs=1e-7)
        assert export["df"][index] == pytest.approx(fract[(name, "Df")])
    assert out.info["testable"] == {"a": True, "b": True, "c": False, "d": False}
