"""R oracle for 1.14.0 lda, corresp, nestedness and renyi operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.corresp import CorrespStep
from src.task.step.steps.lda import LdaStep
from src.task.step.steps.nestedness import NestednessStep
from src.task.step.steps.renyi import RenyiStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")


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


def _align(scores, reference):
    aligned = np.array(scores, dtype=float)
    reference = np.asarray(reference, dtype=float)
    for j in range(aligned.shape[1]):
        pivot = int(np.argmax(np.abs(reference[:, j])))
        if np.sign(aligned[pivot, j]) != np.sign(reference[pivot, j]):
            aligned[:, j] *= -1.0
    return aligned


R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
inp <- args[1]
out <- args[2]
library(MASS)
library(vegan)

x <- as.matrix(read.csv(file.path(inp, "lda_x.csv"), row.names = 1))
g <- read.csv(file.path(inp, "lda_g.csv"), row.names = 1)[, 1]
fit <- lda(x, grouping = g)
pred <- predict(fit, x)
write.csv(fit$scaling, file.path(out, "lda_scaling.csv"))
write.csv(fit$svd, file.path(out, "lda_svd.csv"))
write.csv(pred$x, file.path(out, "lda_scores.csv"))
write.csv(pred$posterior, file.path(out, "lda_posterior.csv"))
write.csv(pred$class, file.path(out, "lda_class.csv"))

tab <- as.matrix(read.csv(file.path(inp, "corresp.csv"), row.names = 1))
ca <- corresp(tab, nf = 2)
write.csv(ca$rscore, file.path(out, "corresp_rows.csv"))
write.csv(ca$cscore, file.path(out, "corresp_cols.csv"))
write.csv(ca$cor, file.path(out, "corresp_cor.csv"))

comm <- as.matrix(read.csv(file.path(inp, "comm.csv"), row.names = 1))
nn <- nestednodf(comm, order = TRUE, weighted = FALSE)
options(digits = 17)
file.create(file.path(out, "nested.csv"))
stat <- nn[["statistic"]]
cat(as.numeric(stat["N.columns"]), as.numeric(stat["N.rows"]),
    as.numeric(stat["NODF"]), as.numeric(nn[["fill"]]), sep = ",",
    file = file.path(out, "nested.csv"), append = TRUE)

ab <- as.matrix(read.csv(file.path(inp, "abundance.csv"), row.names = 1))
rr <- renyi(ab, scales = c(0, 0.5, 1, 2))
write.csv(rr, file.path(out, "renyi.csv"))
"""


def _write_inputs(path):
    x1 = [1, 2, 2, 3, 5, 6, 6, 7, 9, 9, 10, 11]
    x2 = [2, 1, 3, 4, 9, 8, 10, 9, 1, 2, 1, 3]
    samples = [f"s{i}" for i in range(12)]
    lines = ["x1,x2"] + [f"{s},{a},{b}" for s, (a, b) in
                         zip(samples, zip(x1, x2))]
    (path / "lda_x.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    lines = ["g"] + [f"{s},{i // 4}" for i, s in enumerate(samples)]
    (path / "lda_g.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    table = [[10, 5, 0], [2, 8, 4], [0, 3, 7]]
    lines = ["X,Y,Z"] + [f"{row},{a},{b},{c}" for row, (a, b, c) in
                         zip(["A", "B", "C"], table)]
    (path / "corresp.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    comm = [[1, 1, 1, 0, 0], [1, 1, 0, 0, 0], [1, 1, 1, 1, 0],
            [1, 0, 0, 0, 0], [1, 1, 1, 0, 1], [0, 0, 0, 0, 0]]
    lines = ["t1,t2,t3,t4,t5"] + [
        ",".join([f"s{i + 1}"] + [str(v) for v in row])
        for i, row in enumerate(comm)]
    (path / "comm.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    ab = [[10, 1, 0, 2], [8, 2, 1, 0], [12, 0, 0, 1],
          [0, 9, 3, 1], [1, 8, 4, 0], [0, 7, 5, 2]]
    lines = ["t1,t2,t3,t4"] + [
        ",".join([f"s{i + 1}"] + [str(v) for v in row])
        for i, row in enumerate(ab)]
    (path / "abundance.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return x1, x2, comm, ab, table


def _read_csv(path):
    text = path.read_text(encoding="utf-8").strip().splitlines()
    header = text[0].split(",")
    rows = []
    for line in text[1:]:
        rows.append([float(v.strip().strip(chr(34))) for v in line.split(",")[1:]])
    return np.asarray(rows), [line.split(",")[0] for line in text[1:]], header


def test_r_oracle_for_new_operators(tmp_path):
    inputs = tmp_path / "in"
    outputs = tmp_path / "out"
    inputs.mkdir()
    outputs.mkdir()
    x1, x2, comm, ab, table = _write_inputs(inputs)
    script = tmp_path / "oracle.R"
    script.write_text(R_CODE, encoding="utf-8")
    proc = subprocess.run(
        [RSCRIPT, str(script), str(inputs), str(outputs)],
        capture_output=True, text=True,
    )
    assert proc.returncode == 0, proc.stderr

    samples = [f"s{i}" for i in range(12)]
    features = _form(np.column_stack([x1, x2]),
                     ["sample", "feature"],
                     {"sample": {s: i for i, s in enumerate(samples)},
                      "feature": {"x1": 0, "x2": 1}})
    labels = _form(np.asarray([i // 4 for i in range(12)])[:, None],
                   ["sample", "label"],
                   {"sample": {s: i for i, s in enumerate(samples)},
                    "label": {"g": 0}})
    lda, _ = _run(LdaStep(), (features, labels), {"target_label": "g"})
    scaling, _, _ = _read_csv(outputs / "lda_scaling.csv")
    np.testing.assert_allclose(np.asarray(lda.info["scaling"]), scaling, rtol=1e-6)
    svd, _, _ = _read_csv(outputs / "lda_svd.csv")
    np.testing.assert_allclose(np.asarray(lda.info["svd"]), svd.ravel(), rtol=1e-9)
    scores, _, _ = _read_csv(outputs / "lda_scores.csv")
    np.testing.assert_allclose(lda.data[:, 3:], scores, atol=1e-5)
    predicted = lda.data[:, 1].astype(int)
    classes, _, _ = _read_csv(outputs / "lda_class.csv")
    assert predicted.tolist() == [int(v) for v in classes.ravel()]

    corresp_form = _form(table, ["row", "column"],
                         {"row": {"A": 0, "B": 1, "C": 2},
                          "column": {"X": 0, "Y": 1, "Z": 2}})
    ca, _ = _run(CorrespStep(), (corresp_form,), {"n_components": 2})
    rows, _, _ = _read_csv(outputs / "corresp_rows.csv")
    np.testing.assert_allclose(_align(ca.data, rows), rows, atol=1e-6)
    cols, _, _ = _read_csv(outputs / "corresp_cols.csv")
    np.testing.assert_allclose(_align(ca.info["column_scores"], cols), cols,
                               atol=1e-6)
    cor, _, _ = _read_csv(outputs / "corresp_cor.csv")
    np.testing.assert_allclose(ca.info["eigenvalues"], cor.ravel(), rtol=1e-9)

    nested_form = _form(comm, ["sample", "taxon"],
                        {"sample": {f"s{i + 1}": i for i in range(6)},
                         "taxon": {f"t{i + 1}": i for i in range(5)}})
    _, export = _run(NestednessStep(), (nested_form,))
    stat = np.loadtxt(outputs / "nested.csv", delimiter=",")
    assert export["N.columns"] == pytest.approx(stat[0], abs=1e-9)
    assert export["N.rows"] == pytest.approx(stat[1], abs=1e-9)
    assert export["NODF"] == pytest.approx(stat[2], abs=1e-9)
    assert export["fill"] == pytest.approx(stat[3], abs=1e-9)

    renyi_form = _form(ab, ["sample", "taxon"],
                       {"sample": {f"s{i + 1}": i for i in range(6)},
                        "taxon": {f"t{i + 1}": i for i in range(4)}})
    renyi, _ = _run(RenyiStep(), (renyi_form,),
                    {"scales": [0, 0.5, 1, 2], "include_inf": False})
    reference, _, _ = _read_csv(outputs / "renyi.csv")
    np.testing.assert_allclose(renyi.data, reference, atol=1e-6)
