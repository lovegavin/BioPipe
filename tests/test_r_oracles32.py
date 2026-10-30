"""Authoritative R checks for 0.48 post-hoc and block tests."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.step.steps.conover_test import ConoverTestStep
from src.task.step.steps.games_howell import GamesHowellStep
from src.task.step.steps.quade_test import QuadeTestStep


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


def _grouped():
    values = np.array([1, 2, 3, 4, 5, 6, 4, 5, 6, 7, 8, 9, 8, 9, 10, 11, 12, 13], dtype=float)
    groups = ["A"] * 6 + ["B"] * 6 + ["C"] * 6
    encoder = LabelEncoder()
    codes = encoder.fit_transform(groups)
    expression = _form(
        values.reshape(1, -1),
        ["feature", "sample"],
        {"feature": {"value": 0}, "sample": {f"s{i}": i for i in range(18)}},
    )
    meta = _form(
        codes.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": {f"s{i}": i for i in range(18)}, "feature": {"group": 0}},
        {"feature": {"group": encoder}},
    )
    return expression, meta


def _quade():
    matrix = np.array(
        [[1, 2, 3], [2, 4, 6], [3, 6, 9], [4, 8, 12], [5, 10, 15]], dtype=float
    )
    return _form(
        matrix,
        ["block", "treatment"],
        {
            "block": {f"b{i}": i for i in range(5)},
            "treatment": {"T1": 0, "T2": 1, "T3": 2},
        },
    )


R_SCRIPT = r"""
suppressPackageStartupMessages(library(DescTools))
suppressPackageStartupMessages(library(PMCMRplus))
x <- c(1,2,3,4,5,6, 4,5,6,7,8,9, 8,9,10,11,12,13)
g <- factor(rep(c("A","B","C"), each=6))
ct <- ConoverTest(x, g)[[1]]
for (i in seq_len(nrow(ct))) {
  cat(sprintf("CON %s %.17g %.17g\n", rownames(ct)[i], ct[i,1], ct[i,2]))
}
gh <- gamesHowellTest(x, g)
for (nm in c("B-A", "C-A", "C-B")) {
  parts <- strsplit(nm, "-", fixed=TRUE)[[1]]
  cat(sprintf("GAM %s %.17g %.17g\n", nm,
              gh[["statistic"]][parts[1], parts[2]],
              gh[["p.value"]][parts[1], parts[2]]))
}
m <- matrix(c(1,2,3, 2,4,6, 3,6,9, 4,8,12, 5,10,15), nrow=5, byrow=TRUE)
qt <- stats::quade.test(m)
cat(sprintf("QUA %.17g %.17g\n", as.numeric(qt[["statistic"]]), as.numeric(qt[["p.value"]])))
"""


def test_048_operators_match_r(tmp_path):
    rscript = shutil.which("Rscript")
    if not rscript:
        pytest.skip("Rscript not available")
    script = tmp_path / "oracle.R"
    script.write_text(R_SCRIPT, encoding="utf-8")
    proc = subprocess.run([rscript, str(script)], capture_output=True, text=True)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip(proc.stderr.strip())
        raise AssertionError(proc.stderr)

    conover = {}
    games = {}
    quade = None
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "CON":
            conover[parts[1]] = tuple(float(value) for value in parts[2:])
        elif parts[0] == "GAM":
            games[parts[1]] = tuple(float(value) for value in parts[2:])
        elif parts[0] == "QUA":
            quade = tuple(float(value) for value in parts[1:])
    assert set(conover) == {"B-A", "C-A", "C-B"}
    assert set(games) == {"B-A", "C-A", "C-B"}
    assert quade is not None

    expression, meta = _grouped()
    _, out = _run(ConoverTestStep(), {"group_label": "group"}, [expression, meta])
    expected = [conover[name] for name in ("B-A", "C-A", "C-B")]
    assert np.allclose(out.data[:, 0], [-row[0] for row in expected], rtol=1e-6, atol=1e-7)
    assert np.allclose(out.data[:, 2], [row[1] for row in expected], rtol=1e-6, atol=1e-8)

    _, out = _run(GamesHowellStep(), {"group_label": "group"}, [expression, meta])
    expected = [games[name] for name in ("B-A", "C-A", "C-B")]
    assert np.allclose(out.data[:, 1], [row[0] for row in expected], rtol=1e-6, atol=1e-7)
    assert np.allclose(out.data[:, 3], [row[1] for row in expected], rtol=1e-6, atol=1e-8)

    result, _ = _run(QuadeTestStep(), {}, [_quade()])
    assert result["F"] == pytest.approx(quade[0], rel=1e-6)
    assert result["p"] == pytest.approx(quade[1], rel=1e-8)
