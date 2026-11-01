"""R oracle for the 1.17.0 gower, PAM and Nelson-Aalen operators."""
from __future__ import annotations

import csv
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.gower_distance import GowerDistanceStep
from src.task.step.steps.nelson_aalen import NelsonAalenStep
from src.task.step.steps.pam import PamStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

GOWER = np.asarray([
    [1.0, 10.0, 0.0],
    [2.0, 12.0, 0.0],
    [3.5, 9.0, 1.0],
    [4.0, 15.0, 1.0],
    [6.0, 20.0, 2.0],
    [7.5, 18.0, 2.0],
], dtype=np.float64)

PAM_POINTS = np.asarray([
    [0.0, 0.0], [0.3, 0.2], [1.0, 1.2], [1.2, 0.9],
    [5.0, 5.0], [5.4, 4.7], [8.0, 1.0], [8.3, 1.4],
], dtype=np.float64)

SURVIVAL = np.asarray([
    [2.0, 1.0], [3.0, 0.0], [5.0, 1.0], [5.0, 1.0],
    [6.0, 0.0], [8.0, 1.0], [10.0, 0.0], [12.0, 1.0],
], dtype=np.float64)

R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]
out <- args[2]
suppressPackageStartupMessages(library(cluster))
suppressPackageStartupMessages(library(survival))
options(digits = 17)

X <- as.matrix(read.csv(file.path(inp, "gower.csv"), row.names = 1, check.names = FALSE))
df <- data.frame(X[, 1, drop = FALSE])
df <- data.frame(a = X[, "a"], b = X[, "b"], g = factor(X[, "g"]))
d <- daisy(df, metric = "gower")
writeLines(format(as.vector(d), digits = 17), file.path(out, "gower.txt"))

M <- as.matrix(read.csv(file.path(inp, "pam.csv"), row.names = 1, check.names = FALSE))
for (k in c(2, 3)) {
    p <- pam(dist(M), k = k)
    lines <- c(paste(p$clustering, collapse = ","),
               paste(p$id.med, collapse = ","),
               paste(format(p$objective, digits = 17), collapse = ","))
    writeLines(lines, file.path(out, sprintf("pam_%d.txt", k)))
}

S <- as.matrix(read.csv(file.path(inp, "surv.csv"), row.names = 1, check.names = FALSE))
sf <- survfit(Surv(S[, "time"], S[, "status"]) ~ 1, type = "fh")
na <- data.frame(time = sf$time, n.risk = sf$n.risk, n.event = sf$n.event,
                 cumhaz = sf$cumhaz, se = sf$std.err)
write.csv(na, file.path(out, "na.csv"), row.names = FALSE)
"""


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
    form = Form(data=np.asarray(data, dtype=np.float64), dims=list(dims),
                labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _write_matrix(path: Path, matrix, rows, columns):
    lines = ["," + ",".join(columns)]
    for name, row in zip(rows, matrix):
        lines.append(",".join([name] + [format(float(value), ".17g") for value in row]))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_gower_pam_and_nelson_aalen_match_r(tmp_path):
    work = tmp_path / "work"
    work.mkdir()
    _write_matrix(work / "gower.csv", GOWER, [f"s{i}" for i in range(6)],
                  ["a", "b", "g"])
    _write_matrix(work / "pam.csv", PAM_POINTS, [f"s{i}" for i in range(8)],
                  ["x", "y"])
    _write_matrix(work / "surv.csv", SURVIVAL, [f"s{i}" for i in range(8)],
                  ["time", "status"])
    script = work / "oracle.R"
    script.write_text(R_CODE, encoding="utf-8")
    result = subprocess.run([RSCRIPT, str(script), str(work), str(work)],
                            capture_output=True, text=True, timeout=180)
    assert result.returncode == 0, result.stderr

    gower = np.asarray([float(value) for value in
                        (work / "gower.txt").read_text(encoding="utf-8").split()],
                       dtype=np.float64)
    gower_labels = {"sample": {f"s{i}": i for i in range(6)},
                    "feature": {"a": 0, "b": 1, "g": 2}}
    gower_form = _form(GOWER, ["sample", "feature"], gower_labels)
    out, _ = _run(GowerDistanceStep(), [gower_form], {"categorical_labels": ["g"]})
    np.testing.assert_allclose(out.data[np.triu_indices(6, 1)], gower,
                               atol=1e-7, rtol=1e-7)

    pam_labels = {"sample": {f"s{i}": i for i in range(8)},
                  "feature": {"x": 0, "y": 1}}
    pam_form = _form(PAM_POINTS, ["sample", "feature"], pam_labels)
    for k in (2, 3):
        lines = (work / f"pam_{k}.txt").read_text(encoding="utf-8").splitlines()
        clusters = [int(value) for value in lines[0].split(",")]
        medoids = [int(value) - 1 for value in lines[1].split(",")]
        objective = float(lines[2].split(",")[1])
        out, export = _run(PamStep(), [pam_form], {"n_clusters": k})
        assert [int(value) for value in out.data[:, 0]] == clusters
        assert export["medoids"] == medoids
        assert export["objective"] == pytest.approx(objective, rel=1e-9)

    with (work / "na.csv").open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    surv_labels = {"sample": {f"s{i}": i for i in range(8)},
                   "feature": {"time": 0, "status": 1}}
    na_form = _form(SURVIVAL, ["sample", "feature"], surv_labels)
    out, _ = _run(NelsonAalenStep(), [na_form],
                  {"time_label": "time", "event_label": "status"})
    np.testing.assert_allclose(out.data[:, 0], [float(row["n.risk"]) for row in rows],
                               atol=1e-6)
    np.testing.assert_allclose(out.data[:, 1], [float(row["n.event"]) for row in rows],
                               atol=1e-6)
    np.testing.assert_allclose(out.data[:, 2], [float(row["cumhaz"]) for row in rows],
                               atol=1e-6, rtol=1e-6)
    np.testing.assert_allclose(out.data[:, 3], [float(row["se"]) for row in rows],
                               atol=1e-6, rtol=1e-6)
