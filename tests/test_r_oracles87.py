"""R oracle checks for the 1.6.0 community-ecology operators.

The same abundance table, group labels and tree are evaluated with
``vegan::simper``, ``vegan::mrpp``, ``vegan::specaccum`` and
``ape::cophenetic.phylo``, then compared with the Operon operators.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers.newick_reader import NewickReader
from src.task.step.steps.cophenetic_correlation import CopheneticCorrelationStep
from src.task.step.steps.mrpp import MrppStep
from src.task.step.steps.simper import SimperStep
from src.task.step.steps.specaccum import SpecaccumStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
comm <- as.matrix(read.csv(args[1], header = FALSE))
colnames(comm) <- paste0("t", seq_len(ncol(comm)))
grp <- factor(readLines(args[2]))
suppressPackageStartupMessages(library(vegan))
sp <- simper(comm, grp, permutations = 0)[[1]]
lines <- c(
  paste0("simper_average=", paste(format(sp$average, digits = 15), collapse = ",")),
  paste0("simper_ava=", paste(format(sp$ava, digits = 15), collapse = ",")),
  paste0("simper_avb=", paste(format(sp$avb, digits = 15), collapse = ",")),
  paste0("simper_overall=", format(sp$overall, digits = 15))
)
mp <- mrpp(comm, grp, permutations = 0)
lines <- c(lines,
  paste0("mrpp_delta=", format(mp$delta, digits = 15)),
  paste0("mrpp_edelta=", format(mp$E.delta, digits = 15))
)
sa <- specaccum(comm, method = "exact", conditioned = TRUE)
lines <- c(lines,
  paste0("spec_richness=", paste(format(sa$richness, digits = 15), collapse = ",")),
  paste0("spec_sd=", paste(format(sa$sd, digits = 15), collapse = ","))
)
suppressPackageStartupMessages(library(ape))
tr <- read.tree(text = "((A:1,B:1):1,(C:2,D:2):2);")
cm <- cophenetic.phylo(tr)
lines <- c(lines,
  paste0("coph_tree=", paste(format(cm[lower.tri(cm)], digits = 15), collapse = ","))
)
writeLines(lines, args[3])
"""

COUNTS = np.array([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=float)
GROUPS = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
SAMPLES = [f"s{i}" for i in range(6)]
TAXA = ["t1", "t2", "t3", "t4"]
TREE = "((A:1,B:1):1,(C:2,D:2):2);"
COPH_LABELS = ["A", "B", "C", "D"]
COPH_OBSERVED = np.array(
    [[0, 2, 5, 6], [2, 0, 6, 6], [5, 6, 0, 4], [6, 6, 4, 0]], dtype=float
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = dict(params)
        self.metadata = {}


def _form(data, dims, labels):
    out = Form(
        data=np.asarray(data, dtype=np.float32),
        dims=list(dims),
        labels=labels,
        info={"missing_code": np.nan},
    )
    out.validate()
    return out


def _abundance():
    return _form(
        COUNTS,
        ["sample", "taxon"],
        {
            "sample": {name: index for index, name in enumerate(SAMPLES)},
            "taxon": {name: index for index, name in enumerate(TAXA)},
        },
    )


def _meta():
    return _form(
        np.asarray(GROUPS, dtype=float).reshape(-1, 1),
        ["sample", "feature"],
        {
            "sample": {name: index for index, name in enumerate(SAMPLES)},
            "feature": {"group": 0},
        },
    )


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    out = ctx[params["output"]]
    out.validate()
    return out, step.export(ctx)


def _parse(path):
    values = {}
    for line in path.read_text().splitlines():
        if "=" not in line:
            continue
        key, raw = line.split("=", 1)
        if "," in raw:
            values[key] = [float(item) for item in raw.split(",")]
        else:
            values[key] = float(raw)
    return values


def test_r_oracle_community_ecology(tmp_path):
    comm = tmp_path / "comm.csv"
    groups = tmp_path / "groups.txt"
    output = tmp_path / "oracle.txt"
    np.savetxt(comm, COUNTS, delimiter=",", fmt="%.17g")
    groups.write_text("\n".join(f"{value:g}" for value in GROUPS) + "\n")
    script = tmp_path / "oracle.R"
    script.write_text(R_CODE)
    subprocess.run(
        [RSCRIPT, str(script), str(comm), str(groups), str(output)],
        check=True,
        capture_output=True,
        text=True,
    )
    values = _parse(output)

    table, meta = _abundance(), _meta()
    simper, exported = _run(
        SimperStep(),
        {"group_label": "group", "group_a": "0", "group_b": "1", "output": "simper"},
        [table, meta],
    )
    names = simper.labels["statistic"]
    assert np.allclose(
        np.asarray(simper.data[:, names["average"]], dtype=float),
        values["simper_average"],
        atol=1e-6,
    )
    assert np.allclose(
        np.asarray(simper.data[:, names["ava"]], dtype=float), values["simper_ava"], atol=1e-6
    )
    assert np.allclose(
        np.asarray(simper.data[:, names["avb"]], dtype=float), values["simper_avb"], atol=1e-6
    )
    assert np.isclose(exported["overall"], values["simper_overall"], atol=1e-10)

    mrpp, mrpp_exported = _run(
        MrppStep(),
        {"group_label": "group", "n_perm": 99, "random_state": 5, "output": "mrpp"},
        [table, meta],
    )
    assert np.isclose(mrpp_exported["delta"], values["mrpp_delta"], atol=1e-9)
    assert np.isclose(mrpp_exported["E_delta"], values["mrpp_edelta"], atol=1e-9)
    assert np.isclose(mrpp_exported["A"], 1.0 - values["mrpp_delta"] / values["mrpp_edelta"],
                      atol=1e-12)

    curve, curve_exported = _run(SpecaccumStep(), {"output": "curve"}, [table])
    curve_names = curve.labels["statistic"]
    assert np.allclose(
        np.asarray(curve.data[:, curve_names["richness"]], dtype=float),
        values["spec_richness"],
        atol=1e-6,
    )
    # vegan's exact variance can be a tiny negative round-off for a exactly
    # zero variance sample; it reports NaN there, the operator clamps to 0.
    oracle_sd = np.nan_to_num(np.asarray(values["spec_sd"], dtype=float), nan=0.0)
    np.testing.assert_allclose(
        np.asarray(curve.data[:, curve_names["sd"]], dtype=float),
        oracle_sd,
        atol=1e-6,
    )

    tree_path = tmp_path / "tree.nwk"
    tree_path.write_text(TREE)
    tree = NewickReader().read(tree_path, ["node", "field"], {})
    tree.validate()
    observed = _form(
        COPH_OBSERVED,
        ["sample", "sample_b"],
        {
            "sample": {name: index for index, name in enumerate(COPH_LABELS)},
            "sample_b": {name: index for index, name in enumerate(COPH_LABELS)},
        },
    )
    _coph, coph_exported = _run(
        CopheneticCorrelationStep(),
        {"output": "cophenetic_correlation"},
        [tree, observed],
    )
    expected_r = float(np.corrcoef(np.asarray(values["coph_tree"]), COPH_OBSERVED[np.tril_indices(4, -1)])[0, 1])
    assert np.isclose(coph_exported["r"], expected_r, atol=1e-12)
