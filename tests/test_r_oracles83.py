"""R oracle for hierarchical clustering."""

from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.hierarchical_clustering import (
    HierarchicalClusteringStep,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


FIXTURE = np.asarray(
    [[0, 0], [1, 0], [0, 1], [3, 3], [3, 4], [4, 3]], dtype=np.float64
)


def _form():
    return Form(
        data=FIXTURE,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(FIXTURE.shape[0])},
            "feature": {"x": 0, "y": 1},
        },
        info={"missing_code": np.nan},
    )


def test_hierarchical_clustering_matches_r_hclust(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    values_path = tmp_path / "values.csv"
    script_path = tmp_path / "fit.R"
    np.savetxt(values_path, FIXTURE, delimiter=",", header="x,y", comments="")
    script = f"""
x <- as.matrix(read.csv("{values_path}", check.names=FALSE))
d <- dist(x)
methods <- c("single", "complete", "average", "ward.D2")
for (m in methods) {{
  hc <- hclust(d, method=m)
  heights <- paste(sprintf("%.17g", hc[["height"]]), collapse=",")
  labels <- paste(cutree(hc, k=3), collapse="")
  coph <- cor(cophenetic(hc), d)
  cat(sprintf("%s|%s|%s|%.17g\\n", m, heights, labels, coph))
}}
"""
    script_path.write_text(script, encoding="utf-8")
    completed = subprocess.run(
        ["Rscript", str(script_path)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stderr
    reference = {}
    for line in completed.stdout.splitlines():
        method, heights, labels, coph = line.split("|")
        reference[method] = (
            [float(value) for value in heights.split(",")],
            [int(value) - 1 for value in labels],
            float(coph),
        )

    for method, (heights, labels, coph) in reference.items():
        ctx = Ctx({"linkage": method, "n_clusters": 3, "output": "clusters"})
        step = HierarchicalClusteringStep()
        step.run(ctx, [_form()])
        export = step.export(ctx)
        assert export["heights"] == pytest.approx(heights, abs=1e-12)
        assert export["labels"] == labels
        assert export["cophenetic_correlation"] == pytest.approx(coph, abs=1e-12)
