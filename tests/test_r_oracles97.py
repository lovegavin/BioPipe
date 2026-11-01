"""R oracle for the 1.16.0 bioenv and Morisita operators."""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.bioenv import BioenvStep
from src.task.step.steps.morisita import MorisitaStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

COMMUNITY = np.asarray([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=np.float64)

ENV = np.asarray([
    [1.234, 5.217, 0.201],
    [2.591, 7.903, 0.374],
    [4.113, 3.411, 0.618],
    [6.702, 2.098, 1.027],
    [8.319, 1.612, 1.639],
    [11.427, 0.407, 2.751],
], dtype=np.float64)

MORISITA = np.asarray([
    [5, 0, 2],
    [3, 1, 0],
    [0, 4, 1],
    [2, 2, 3],
    [1, 3, 0],
], dtype=np.float64)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, inputs, params=None):
    ctx = Ctx(params or {})
    step.run(ctx, inputs)
    return ctx["out"]


def _form(data, dims, labels):
    form = Form(data=np.asarray(data, dtype=np.float64), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _write_matrix(path: Path, matrix, rows, columns):
    lines = ["," + ",".join(columns)]
    for name, row in zip(rows, matrix):
        lines.append(",".join([name] + [format(float(value), ".17g") for value in row]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_rows(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]
out <- args[2]
suppressPackageStartupMessages(library(vegan))
options(digits = 17)
comm <- as.matrix(read.csv(file.path(inp, "comm.csv"), row.names = 1, check.names = FALSE))
env <- as.matrix(read.csv(file.path(inp, "env.csv"), row.names = 1, check.names = FALSE))
res <- bioenv(comm, env, upto = ncol(env))
lines <- c("size,rho,variables")
for (i in seq_along(res$models)) {
    model <- res$models[[i]]
    names <- paste(colnames(env)[model$best], collapse = "|")
    lines <- c(lines, paste(i, format(model$est, digits = 17), names, sep = ","))
}
writeLines(lines, file.path(out, "bioenv.csv"))
disp <- as.matrix(read.csv(file.path(inp, "disp.csv"), row.names = 1, check.names = FALSE))
mo <- dispindmorisita(disp)
lines <- c("species,imor,mclu,muni,imst,pchisq")
for (i in seq_len(nrow(mo))) {
    values <- paste(format(as.numeric(mo[i, ]), digits = 17), collapse = ",")
    lines <- c(lines, paste(colnames(disp)[i], values, sep = ","))
}
writeLines(lines, file.path(out, "morisita.csv"))
"""


def test_bioenv_and_morisita_match_vegan(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _write_matrix(work / "comm.csv", COMMUNITY, [f"s{i}" for i in range(6)],
                  [f"t{i}" for i in range(4)])
    _write_matrix(work / "env.csv", ENV, [f"s{i}" for i in range(6)],
                  ["x", "y", "z"])
    _write_matrix(work / "disp.csv", MORISITA, [f"s{i}" for i in range(5)],
                  [f"sp{i}" for i in range(3)])
    script = work / "oracle.R"
    script.write_text(R_CODE, encoding="utf-8")
    result = subprocess.run(
        [RSCRIPT, str(script), str(work), str(work)],
        capture_output=True, text=True, timeout=180,
    )
    assert result.returncode == 0, result.stderr
    entries = {row["size"]: row for row in _read_rows(work / "bioenv.csv")}
    community = _form(COMMUNITY, ["sample", "taxon"],
                      {"sample": {f"s{i}": i for i in range(6)},
                       "taxon": {f"t{i}": i for i in range(4)}})
    env = _form(ENV, ["sample", "env"],
                {"sample": {f"s{i}": i for i in range(6)},
                 "env": {"x": 0, "y": 1, "z": 2}})
    out = _run(BioenvStep(), (community, env))
    for index, row in entries.items():
        position = out.labels["size"][index]
        assert out.data[position, 0] == pytest.approx(float(row["rho"]), rel=1e-5)
        expected = row["variables"].split("|")
        assert out.info["models"][position]["variables"] == expected
    morisita = _form(MORISITA, ["sample", "feature"],
                     {"sample": {f"s{i}": i for i in range(5)},
                      "feature": {f"sp{i}": i for i in range(3)}})
    out = _run(MorisitaStep(), (morisita,))
    rows = _read_rows(work / "morisita.csv")
    assert len(rows) == 3
    for row in rows:
        position = out.labels["feature"][row["species"]]
        expected = [float(row[name]) for name in
                    ("imor", "mclu", "muni", "imst", "pchisq")]
        np.testing.assert_allclose(out.data[position], expected,
                                   rtol=1e-5, atol=1e-7)
