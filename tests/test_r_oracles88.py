"""R oracle checks for Moran's I and indicator species.

``ape::Moran.I`` and ``labdsv::indval`` are evaluated on the same fixed
fixtures as the Operon operators.
"""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.indicator_species import IndicatorSpeciesStep
from src.task.step.steps.moran import MoranStep

RSCRIPT = shutil.which("Rscript")
pytestmark = pytest.mark.skipif(RSCRIPT is None, reason="Rscript is not available")

R_CODE = r"""
args <- commandArgs(trailingOnly = TRUE)
x <- scan(args[1], quiet = TRUE)
d <- as.matrix(read.csv(args[2], header = FALSE))
w <- 1 / d
w[!is.finite(w)] <- 0
diag(w) <- 0
suppressPackageStartupMessages(library(ape))
mi <- Moran.I(x, w, alternative = "two.sided")
comm <- as.matrix(read.csv(args[3], header = FALSE))
grp <- factor(readLines(args[4]))
suppressPackageStartupMessages(library(labdsv))
iv <- indval(comm, grp, numitr = 0)
lines <- c(
  paste0("moran_observed=", format(mi$observed, digits = 15)),
  paste0("moran_expected=", format(mi$expected, digits = 15)),
  paste0("moran_sd=", format(mi$sd, digits = 15)),
  paste0("moran_p=", format(mi$p.value, digits = 15)),
  paste0("indval=", paste(format(t(iv$indval), digits = 15), collapse = ",")),
  paste0("maxcls=", paste(iv$maxcls, collapse = ",")),
  paste0("indcls=", paste(format(iv$indcls, digits = 15), collapse = ","))
)
writeLines(lines, args[5])
"""

MORAN_X = [1.0, 2.0, 4.0, 3.0, 5.0]
MORAN_LABELS = [f"s{i}" for i in range(5)]
IND_COUNTS = np.array([
    [10, 1, 0, 2],
    [8, 2, 1, 0],
    [12, 0, 0, 1],
    [0, 9, 3, 1],
    [1, 8, 4, 0],
    [0, 7, 5, 2],
], dtype=float)
IND_GROUPS = [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
IND_TAXA = ["t1", "t2", "t3", "t4"]
IND_SAMPLES = [f"s{i}" for i in range(6)]


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
        values[key] = [float(item) for item in raw.split(",")] if "," in raw else float(raw)
    return values


def test_r_oracle_moran_and_indicator(tmp_path):
    x_path = tmp_path / "values.txt"
    distance_path = tmp_path / "distance.csv"
    counts_path = tmp_path / "counts.csv"
    groups_path = tmp_path / "groups.txt"
    output_path = tmp_path / "oracle.txt"
    x_path.write_text("\n".join(f"{value:g}" for value in MORAN_X) + "\n")
    distances = np.abs(np.arange(5)[:, None] - np.arange(5)[None, :])
    np.savetxt(distance_path, distances, delimiter=",", fmt="%d")
    np.savetxt(counts_path, IND_COUNTS, delimiter=",", fmt="%.17g")
    groups_path.write_text("\n".join(f"{value:g}" for value in IND_GROUPS) + "\n")
    script = tmp_path / "oracle.R"
    script.write_text(R_CODE)
    subprocess.run(
        [RSCRIPT, str(script), str(x_path), str(distance_path), str(counts_path),
         str(groups_path), str(output_path)],
        check=True,
        capture_output=True,
        text=True,
    )
    values = _parse(output_path)

    table = _form(
        np.asarray(MORAN_X).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(MORAN_LABELS)}, "feature": {"value": 0}},
    )
    weights = _form(
        distances,
        ["sample", "sample_b"],
        {"sample": {name: i for i, name in enumerate(MORAN_LABELS)},
         "sample_b": {name: i for i, name in enumerate(MORAN_LABELS)}},
    )
    moran, _exported = _run(MoranStep(), {"output": "moran"}, [table, weights])
    names = moran.labels["statistic"]
    for key, name in (("moran_observed", "observed"), ("moran_expected", "expected"),
                      ("moran_sd", "sd"), ("moran_p", "p_value")):
        assert np.isclose(float(moran.data[names[name], 0]), values[key], atol=1e-9), name

    abundance = _form(
        IND_COUNTS,
        ["sample", "taxon"],
        {"sample": {name: i for i, name in enumerate(IND_SAMPLES)},
         "taxon": {name: i for i, name in enumerate(IND_TAXA)}},
    )
    meta = _form(
        np.asarray(IND_GROUPS).reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {name: i for i, name in enumerate(IND_SAMPLES)}, "feature": {"group": 0}},
    )
    indicator, exported = _run(
        IndicatorSpeciesStep(),
        {"group_label": "group", "output": "indicator_species"},
        [abundance, meta],
    )
    statistic = indicator.labels["statistic"]
    # R pastes t(indval) in column-major order: all groups of the first
    # taxon, then all groups of the second taxon, and so on.
    expected_matrix = np.asarray(values["indval"], dtype=float).reshape(len(IND_TAXA), -1)
    for group_index, group in enumerate(["0", "1"]):
        observed = np.asarray(indicator.data[:, statistic[f"indval:{group}"]], dtype=float)
        assert np.allclose(observed, expected_matrix[:, group_index], atol=1e-8), group
    max_class = np.asarray(indicator.data[:, statistic["group_max"]], dtype=float)
    assert max_class.tolist() == [float(value) - 1.0 for value in values["maxcls"]]
    assert np.allclose(
        np.asarray(indicator.data[:, statistic["indval_max"]], dtype=float),
        np.asarray(values["indcls"], dtype=float),
        atol=1e-7,
    )
    assert np.isclose(exported["max_indval"], max(values["indcls"]), atol=1e-9)
