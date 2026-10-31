"""R oracle checks for 0.82 PCoA and CCA."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.cca import CcaStep
from src.task.step.steps.pcoa import PcoaStep

DISTANCE = np.array(
    [
        [0, 1, 1, 2, 1, 2, 2],
        [1, 0, 2, 1, 2, 1, 3],
        [1, 2, 0, 1, 3, 1, 1],
        [2, 1, 1, 0, 1, 3, 1],
        [1, 2, 3, 1, 0, 2, 2],
        [2, 1, 1, 3, 2, 0, 2],
        [2, 3, 1, 1, 2, 2, 0],
    ],
    dtype=float,
)
Y = np.array(
    [
        [10, 20, 30],
        [20, 40, 20],
        [30, 10, 10],
        [15, 25, 35],
        [25, 15, 20],
        [5, 30, 25],
        [20, 20, 40],
        [30, 20, 10],
    ],
    dtype=float,
)
X = np.column_stack(
    [
        [-1, -0.5, 0, 0.5, 1, -1, 0, 1],
        [0, 1, 0, 1, 0, 1, 1, 0],
    ]
)


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx)


def _form(values, dims, labels):
    form = Form(data=np.asarray(values, dtype=float), dims=dims, labels=labels, info={"missing_code": np.nan})
    form.validate()
    return form


def _require_r_package(package: str) -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", f'cat(requireNamespace("{package}", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip(f"R {package} is not available")


def test_pcoa_matches_r_cmdscale(tmp_path):
    _require_r_package("vegan")
    pd.DataFrame(DISTANCE).to_csv(tmp_path / "d.csv", index=False, header=False)
    script = f"""
d <- as.matrix(read.csv("{tmp_path.as_posix()}/d.csv", header=FALSE))
p <- cmdscale(d, k=4, eig=TRUE)
write.csv(data.frame(eig=as.numeric(p$eig)),
          file="{tmp_path.as_posix()}/eig.csv", row.names=FALSE)
write.csv(data.frame(p$points), file="{tmp_path.as_posix()}/pts.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    eig = pd.read_csv(tmp_path / "eig.csv")["eig"].to_numpy()
    points = pd.read_csv(tmp_path / "pts.csv").to_numpy()
    export = _run(
        PcoaStep(),
        {"n_components": 4, "output": "p"},
        [
            _form(
                DISTANCE,
                ["sample", "sample_b"],
                {
                    "sample": {f"s{i}": i for i in range(7)},
                    "sample_b": {f"s{i}": i for i in range(7)},
                },
            )
        ],
    )
    positive = eig[eig > 1e-8]
    np.testing.assert_allclose(export["eigenvalues"], positive, rtol=0, atol=1e-8)
    np.testing.assert_allclose(
        np.abs(np.asarray(export["coordinates"])[:, :3]),
        np.abs(points[:, :3]),
        rtol=0,
        atol=1e-5,
    )


def test_cca_matches_r_vegan(tmp_path):
    _require_r_package("vegan")
    pd.DataFrame(Y, index=[f"s{i}" for i in range(8)]).to_csv(tmp_path / "y.csv")
    pd.DataFrame(X, index=[f"s{i}" for i in range(8)], columns=["x1", "x2"]).to_csv(
        tmp_path / "x.csv"
    )
    script = f"""
suppressPackageStartupMessages(library(vegan))
Y <- as.matrix(read.csv("{tmp_path.as_posix()}/y.csv", row.names=1, check.names=FALSE))
X <- read.csv("{tmp_path.as_posix()}/x.csv", row.names=1, check.names=FALSE)
f <- cca(Y ~ ., data=X)
write.csv(data.frame(eig=as.numeric(f$CCA$eig)),
          file="{tmp_path.as_posix()}/eig.csv", row.names=FALSE)
write.csv(data.frame(total=f$tot.chi, constrained=f$CCA$tot.chi,
                     unconstrained=f$CA$tot.chi),
          file="{tmp_path.as_posix()}/inertia.csv", row.names=FALSE)
"""
    result = subprocess.run(["Rscript", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    eig = pd.read_csv(tmp_path / "eig.csv")["eig"].to_numpy()
    inertia = pd.read_csv(tmp_path / "inertia.csv").iloc[0]
    export = _run(
        CcaStep(),
        {"n_components": 2, "output": "c"},
        [
            _form(
                Y,
                ["sample", "feature"],
                {
                    "sample": {f"s{i}": i for i in range(8)},
                    "feature": {"sp1": 0, "sp2": 1, "sp3": 2},
                },
            ),
            _form(
                X,
                ["sample", "predictor"],
                {
                    "sample": {f"s{i}": i for i in range(8)},
                    "predictor": {"x1": 0, "x2": 1},
                },
            ),
        ],
    )
    np.testing.assert_allclose(export["eigenvalues"], eig, rtol=0, atol=1e-10)
    assert export["total_inertia"] == pytest.approx(float(inertia["total"]), abs=1e-10)
    assert export["constrained_inertia"] == pytest.approx(
        float(inertia["constrained"]), abs=1e-10
    )
    assert export["unconstrained_inertia"] == pytest.approx(
        float(inertia["unconstrained"]), abs=1e-10
    )
