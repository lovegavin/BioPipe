from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.envfit import EnvfitStep


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[params.get("output", step.name)], step.export(ctx)


def test_envfit_matches_vegan(tmp_path):
    rscript = shutil.which("Rscript")
    if rscript is None:
        pytest.skip("Rscript is not installed")
    probe = subprocess.run(
        [rscript, "-e", "cat(requireNamespace('vegan', quietly=TRUE))"],
        capture_output=True,
        text=True,
    )
    if probe.returncode != 0 or probe.stdout.strip() != "TRUE":
        pytest.skip("R package vegan is not installed")

    rng = np.random.default_rng(20261119)
    n = 30
    o1 = np.linspace(-2, 2, n)
    o2 = rng.normal(size=n)
    e1 = 0.8 * o1 - 0.2 * o2 + rng.normal(scale=0.4, size=n)
    e2 = -0.3 * o1 + 0.7 * o2 + rng.normal(scale=0.5, size=n)
    e3 = rng.normal(size=n)
    path = tmp_path / "envfit.csv"
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["o1", "o2", "e1", "e2", "e3"])
        for row in zip(o1, o2, e1, e2, e3):
            writer.writerow([f"{v:.17g}" for v in row])

    script = tmp_path / "envfit.R"
    script.write_text(
        "\n".join(
            [
                f'd <- read.csv("{path.as_posix()}", check.names=FALSE)',
                'ord <- as.matrix(d[, c("o1", "o2")])',
                'env <- d[, c("e1", "e2", "e3")]',
                "ef <- vegan::envfit(ord, env, permutations=0)",
                "r <- ef$vectors$r",
                "a <- ef$vectors$arrows",
                "for (i in seq_along(r)) cat(sprintf('%.15g %.15g %.15g\\n', r[i], a[i, 1], a[i, 2]))",
            ]
        ),
        encoding="utf-8",
    )
    result = subprocess.run(
        [rscript, str(script)],
        capture_output=True,
        text=True,
        check=True,
        cwd=tmp_path,
    )
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) == 3:
            try:
                rows.append([float(v) for v in parts])
            except ValueError:
                pass
    assert len(rows) == 3, result.stdout

    samples = [f"s{i}" for i in range(n)]
    fx = _form(
        np.column_stack([o1, o2]),
        ["sample", "component"],
        {"sample": _labels(samples), "component": _labels(["axis1", "axis2"])},
    )
    fy = _form(
        np.column_stack([e1, e2, e3]),
        ["sample", "feature"],
        {"sample": _labels(samples), "feature": _labels(["e1", "e2", "e3"])},
    )
    out, info = _run(EnvfitStep(), {}, [fx, fy])
    for i, feature in enumerate(["e1", "e2", "e3"]):
        assert info["r2"][feature] == pytest.approx(rows[i][0], abs=1e-5)
        assert info["arrows"][feature][0] == pytest.approx(rows[i][1], abs=1e-5)
        assert info["arrows"][feature][1] == pytest.approx(rows[i][2], abs=1e-5)
        assert out.data[i, 0] == pytest.approx(rows[i][0], abs=1e-4)
