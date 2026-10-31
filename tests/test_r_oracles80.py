"""R oracles for 0.100 additive B-spline GLM."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pandas as pd
import pytest

from src.core import Form
from src.task.step.steps.additive_glm import AdditiveGlmStep

RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data):
    form = Form(
        data=np.asarray(data, dtype=float),
        dims=["sample", "feature"],
        labels={
            "sample": {f"s{i}": i for i in range(data.shape[0])},
            "feature": {"x1": 0, "x2": 1, "y": 2},
        },
        info={"missing_code": np.nan},
    )
    form.validate()
    return form


def _python_fit(x1, x2, y, family):
    ctx = Ctx({
        "response_label": "y",
        "predictors": ["x1", "x2"],
        "family": family,
        "df": 4,
        "output": "fit",
    })
    step = AdditiveGlmStep()
    step.run(ctx, [_form(np.column_stack([x1, x2, y]))])
    return step.export(ctx)


def _r_fit(tmp_path, x1, x2, y, family):
    data = pd.DataFrame({"x1": x1, "x2": x2, "y": y})
    source = tmp_path / "input.csv"
    output = tmp_path / "r.csv"
    data.to_csv(source, index=False)
    script = f"""
d <- read.csv({str(source)!r})
fit <- glm(y ~ splines::bs(x1, df=4) + splines::bs(x2, df=4),
           data=d, family={family}())
out <- data.frame(fitted=predict(fit, type='response'),
                  linear=predict(fit, type='link'))
write.csv(out, {str(output)!r}, row.names=FALSE)
"""
    proc = subprocess.run(
        ["Rscript", "-e", script],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        pytest.fail(f"Rscript failed:\n{proc.stdout}\n{proc.stderr}")
    return pd.read_csv(output)


def _binomial_fixture():
    rng = np.random.default_rng(20261120)
    x1 = rng.normal(size=120)
    x2 = rng.uniform(-1.0, 1.0, size=120)
    eta = -0.2 + 1.1 * np.sin(x1 * 1.2) - 0.7 * x2 ** 2 + 0.4 * x1
    y = rng.binomial(1, 1.0 / (1.0 + np.exp(-eta))).astype(float)
    return x1, x2, y


def _poisson_fixture():
    rng = np.random.default_rng(20261121)
    x1 = rng.normal(size=110)
    x2 = rng.uniform(-1.0, 1.0, size=110)
    eta = 0.3 + 0.5 * np.sin(x1) - 0.2 * x2 + 0.15 * x1
    y = rng.poisson(np.exp(eta)).astype(float)
    return x1, x2, y


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not available")
def test_additive_glm_binomial_matches_r(tmp_path):
    x1, x2, y = _binomial_fixture()
    export = _python_fit(x1, x2, y, "binomial")
    truth = _r_fit(tmp_path, x1, x2, y, "binomial")
    np.testing.assert_allclose(
        export["fitted"], truth["fitted"], rtol=0, atol=1e-8
    )
    np.testing.assert_allclose(
        export["linear_predictor"], truth["linear"], rtol=0, atol=1e-8
    )


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not available")
def test_additive_glm_poisson_matches_r(tmp_path):
    x1, x2, y = _poisson_fixture()
    export = _python_fit(x1, x2, y, "poisson")
    truth = _r_fit(tmp_path, x1, x2, y, "poisson")
    np.testing.assert_allclose(
        export["fitted"], truth["fitted"], rtol=0, atol=1e-8
    )
    np.testing.assert_allclose(
        export["linear_predictor"], truth["linear"], rtol=0, atol=1e-8
    )
