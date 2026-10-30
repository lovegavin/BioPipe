"""Authoritative R checks for the 0.46 multivariate operators."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.box_m import BoxMStep
from src.task.step.steps.mahalanobis_distance import MahalanobisDistanceStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels, encoders=None):
    form = Form(
        np.asarray(data, dtype=np.float64),
        list(dims),
        labels,
        {"missing_code": np.nan, "encoders": encoders or {}},
    )
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _mahal_form():
    x = np.array([
        [2, 3, 1], [3, 1, 3], [4, 6, 2], [5, 2, 5],
        [6, 8, 4], [7, 4, 7], [8, 10, 6], [9, 5, 9],
    ], dtype=float)
    return x, _form(
        x,
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(8)}, "feature": {"x1": 0, "x2": 1, "x3": 2}},
    )


def _box_form():
    a = np.array([[1, 2], [2, 1], [3, 3], [2, 4], [4, 2], [3, 5], [5, 3], [4, 4]], dtype=float)
    b = np.array([[5, 7], [6, 5], [7, 8], [6, 9], [8, 6], [7, 7], [9, 8], [8, 9]], dtype=float)
    c = np.array([[10, 1], [11, 3], [12, 2], [10, 4], [13, 3], [11, 5], [12, 4], [14, 2]], dtype=float)
    values = np.vstack([a, b, c])
    groups = ["A"] * 8 + ["B"] * 8 + ["C"] * 8
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    return values, groups, _form(
        np.column_stack([values, codes]),
        ["sample", "feature"],
        {
            "sample": {f"s{i}": i for i in range(24)},
            "feature": {"v1": 0, "v2": 1, "group": 2},
        },
        {"feature": {"group": encoder}},
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(biotools))
d <- commandArgs(TRUE)[1]
m <- as.matrix(read.csv(file.path(d, "mahal.csv")))
md <- mahalanobis(m, colMeans(m), cov(m))
for (i in seq_along(md)) {
  cat(sprintf("MAHAL %d %.17g\n", i, md[i]))
}
b <- read.csv(file.path(d, "boxm.csv"))
fit <- boxM(b[, c("v1", "v2")], b$group)
cat(sprintf("BOXM %.17g %.17g %.17g\n",
            fit[["statistic"]], fit[["parameter"]], fit[["p.value"]]))
"""


def test_046_operators_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    x, form = _mahal_form()
    np.savetxt(tmp_path / "mahal.csv", x, delimiter=",", header="x1,x2,x3", comments="", fmt="%.17g")
    values, groups, box_form = _box_form()
    pd.DataFrame(values, columns=["v1", "v2"]).assign(group=groups).to_csv(
        tmp_path / "boxm.csv", index=False
    )
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script), str(tmp_path)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)

    mahal = {}
    box = None
    for line in proc.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[0] == "MAHAL":
            mahal[int(parts[1])] = float(parts[2])
        elif len(parts) == 4 and parts[0] == "BOXM":
            box = tuple(float(value) for value in parts[1:])
    assert len(mahal) == 8
    assert box is not None

    _, out = _run(MahalanobisDistanceStep(), {}, [form])
    actual = out.data[:, 0].astype(float)
    expected = np.asarray([mahal[i] for i in range(1, 9)])
    assert np.allclose(actual, expected, rtol=1e-6, atol=1e-7)

    result, _ = _run(BoxMStep(), {"group_label": "group"}, [box_form])
    assert result["chi2"] == pytest.approx(box[0], rel=1e-9)
    assert result["df"] == int(box[1])
    assert result["p"] == pytest.approx(box[2], rel=1e-9)
