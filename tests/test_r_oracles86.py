"""R oracle check for the 1.5.0 PLAGE gene-set scores."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.gsva_plage import GsvaPlageStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
x <- as.matrix(read.csv(args[1], header = FALSE))
genes <- readLines(args[2])
colnames(x) <- paste0("s", seq_len(ncol(x)))
rownames(x) <- genes
sets <- list()
for (line in readLines(args[3])) {
  parts <- strsplit(line, "\t")[[1]]
  sets[[parts[1]]] <- parts[-1]
}
suppressPackageStartupMessages(library(GSVA))
suppressWarnings(es <- gsva(x, sets, method = "plage", verbose = FALSE))
write.table(es, args[4], sep = ",", row.names = TRUE, col.names = TRUE, quote = FALSE)
"""


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _fixture():
    rng = np.random.default_rng(20261102)
    data = rng.normal(size=(8, 6))
    data[1] = 2.0 * data[0] + 0.1 * data[1]
    genes = [f"g{i}" for i in range(1, 9)]
    samples = [f"s{i}" for i in range(1, 7)]
    sets = [
        ("set_a", ["g1", "g2", "g3"]),
        ("set_b", ["g4", "g5"]),
        ("set_c", ["g6", "g7", "g8"]),
    ]
    return data, genes, samples, sets


def _forms(data, genes, samples, sets):
    expr = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=["gene", "sample"],
        labels={
            "gene": {name: index for index, name in enumerate(genes)},
            "sample": {name: index for index, name in enumerate(samples)},
        },
        info={"missing_code": np.nan},
    )
    set_names = [name for name, _ in sets]
    membership = np.zeros((len(genes), len(set_names)), dtype=np.float32)
    for column, (_, members) in enumerate(sets):
        for gene in members:
            membership[genes.index(gene), column] = 1.0
    sets_form = Form(
        data=membership,
        dims=["gene", "gene_set"],
        labels={
            "gene": {name: index for index, name in enumerate(genes)},
            "gene_set": {name: index for index, name in enumerate(set_names)},
        },
        info={"missing_code": np.nan},
    )
    return expr, sets_form


def test_plage_matches_gsva(tmp_path):
    data, genes, samples, sets = _fixture()
    matrix_path = tmp_path / "matrix.csv"
    genes_path = tmp_path / "genes.txt"
    sets_path = tmp_path / "sets.txt"
    scores_path = tmp_path / "scores.csv"
    np.savetxt(matrix_path, data, delimiter=",")
    genes_path.write_text("\n".join(genes) + "\n", encoding="utf-8")
    sets_path.write_text(
        "\n".join(name + "\t" + "\t".join(members) for name, members in sets) + "\n",
        encoding="utf-8",
    )
    script = tmp_path / "oracle.R"
    script.write_text(R_CODE, encoding="utf-8")
    result = subprocess.run(
        [RSCRIPT, str(script), str(matrix_path), str(genes_path), str(sets_path), str(scores_path)],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert result.returncode == 0, result.stderr

    expr, sets_form = _forms(data, genes, samples, sets)
    ctx = Ctx(
        {
            "output": "output",
            "feature_dim": "gene",
            "gene_set_dim": "gene_set",
        }
    )
    GsvaPlageStep().run(ctx, [expr, sets_form])
    out = ctx["output"]

    lines = [line.split(",") for line in scores_path.read_text(encoding="utf-8").strip().splitlines()]
    reference = {row[0]: np.array([float(value) for value in row[1:]]) for row in lines[1:]}
    assert set(reference) == {name for name, _ in sets}
    for column, (name, _) in enumerate(sets):
        mine = np.asarray(out.data[:, column], dtype=np.float64)
        expected = reference[name]
        assert np.allclose(np.abs(mine), np.abs(expected), atol=1e-5, rtol=0), (name, mine, expected)
        correlation = float(np.corrcoef(mine, expected)[0, 1])
        assert abs(abs(correlation) - 1.0) <= 1e-4, (name, correlation)
