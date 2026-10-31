"""Authoritative R checks for 0.57 all-pairs mean comparisons."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.snk_test import SnkTestStep
from src.task.step.steps.tamhane_t2 import TamhaneT2Step
from src.task.step.steps.tukey_test import TukeyTestStep


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
    return ctx[params.get("output", step.name)]


def _grouped():
    values = np.array(
        [
            1, 2, 3, 4, 5,
            2, 4, 6, 8, 10, 12,
            10, 12, 14, 16, 18,
            9, 11, 13, 15, 17, 19, 21,
        ],
        dtype=float,
    )
    groups = ["A"] * 5 + ["B"] * 6 + ["C"] * 5 + ["D"] * 7
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(23)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(23)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


R_SCRIPT = r"""
suppressPackageStartupMessages(library(PMCMRplus))
x <- c(1:5, seq(2, 12, 2), seq(10, 18, 2), seq(9, 21, 2))
g <- factor(rep(c("A", "B", "C", "D"), c(5, 6, 5, 7)), levels = c("A", "B", "C", "D"))
for (spec in list(c("TK", "tukey"), c("TH", "tamhane"), c("SN", "snk"))) {
  r <- switch(spec[2], tukey = tukeyTest(x, g), tamhane = tamhaneT2Test(x, g), snk = snkTest(x, g))
  P <- r[["p.value"]]
  vals <- c(P[1, 1], P[2, 1], P[2, 2], P[3, 1], P[3, 2], P[3, 3])
  cat(spec[1], sprintf("%.17g", vals), "\n")
}
"""


def _load_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    path = tmp_path / "oracle57.R"
    path.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(path)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"TK", "TH", "SN"}:
            values[parts[0]] = [float(value) for value in parts[1:]]
    assert set(values) == {"TK", "TH", "SN"}
    return values


def test_057_tests_match_r(tmp_path):
    values = _load_r(tmp_path)
    expression, meta = _grouped()
    for key, step in (
        ("TK", TukeyTestStep()),
        ("TH", TamhaneT2Step()),
        ("SN", SnkTestStep()),
    ):
        out = _run(step, {"group_label": "group"}, [expression, meta])
        assert out.data[:, 3].tolist() == pytest.approx(values[key], rel=1e-6)
