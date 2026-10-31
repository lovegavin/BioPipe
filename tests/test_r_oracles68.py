"""R oracle checks for 0.86 Chao1 richness and rarefaction."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.chao1 import Chao1Step
from src.task.step.steps.rarefaction import RarefactionStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _run(step, params, form):
    ctx = Ctx(params)
    step.run(ctx, [form])
    return step.export(ctx)


def _form(values):
    values = np.asarray(values, dtype=float)
    form = Form(
        data=values,
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(values.shape[0])},
            "feature": {f"f{i}": i for i in range(values.shape[1])},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _require_vegan() -> None:
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript is not available")
    check = subprocess.run(
        ["Rscript", "-e", 'cat(requireNamespace("vegan", quietly=TRUE))'],
        capture_output=True,
        text=True,
    )
    if check.returncode != 0 or check.stdout.strip() != "TRUE":
        pytest.skip("R vegan is not available")


COUNTS = np.array(
    [
        [10, 20, 30, 0],
        [5, 0, 15, 30],
        [0, 0, 0, 0],
        [1, 1, 1, 1],
    ],
    dtype=float,
)
RARE = np.array(
    [
        [10, 20, 30, 0],
        [5, 0, 15, 30],
        [2, 3, 5, 0],
    ],
    dtype=float,
)


def test_rarefaction_matches_r_vegan(tmp_path):
    _require_vegan()
    rare = RARE
    pd.DataFrame(rare, index=[f"s{i}" for i in range(3)]).to_csv(
        tmp_path / "rare.csv"
    )
    script = f"""
    x <- as.matrix(read.csv("{tmp_path / 'rare.csv'}", row.names=1))
    write.csv(vegan::rarefy(x, 10), "{tmp_path / 'rarefied.csv'}")
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)
    expected = pd.read_csv(tmp_path / "rarefied.csv", index_col=0).iloc[:, 0].to_numpy()
    export = _run(RarefactionStep(), {"depth": 10, "output": "rare"}, _form(rare))
    np.testing.assert_allclose(export["rarefied"], expected, rtol=0, atol=1e-10)


def test_chao1_matches_r_vegan(tmp_path):
    _require_vegan()
    pd.DataFrame(COUNTS, index=[f"s{i}" for i in range(4)]).to_csv(
        tmp_path / "counts.csv"
    )
    script = f"""
    x <- as.matrix(read.csv("{tmp_path / 'counts.csv'}", row.names=1))
    e <- vegan::estimateR(x)
    write.csv(e["S.chao1", ], "{tmp_path / 'chao1.csv'}")
    """
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)
    expected = pd.read_csv(tmp_path / "chao1.csv", index_col=0).iloc[:, 0].to_numpy()
    export = _run(Chao1Step(), {"output": "chao1"}, _form(COUNTS))
    np.testing.assert_allclose(export["chao1"], expected, rtol=0, atol=1e-6)
