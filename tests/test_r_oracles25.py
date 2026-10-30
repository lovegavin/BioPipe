"""R oracle checks for 0.40 Van der Waerden, Bartels and Woolf."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.bartels_rank import BartelsRankStep
from src.task.step.steps.van_waerden import VanWaerdenStep
from src.task.step.steps.woolf_test import WoolfTestStep


class Ctx(dict):
    def __init__(self, params=None):
        super().__init__()
        self.step_params = params or {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float32), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return step.export(ctx), ctx[params.get("output", step.name)]


def _inputs():
    x = np.arange(1.0, 11.0)
    vex = _form(x.reshape(1, -1), ["feature", "sample"], {
        "feature": {"x": 0}, "sample": {f"s{i}": i for i in range(10)},
    })
    vmeta = _form([[0]] * 5 + [[1]] * 5, ["sample", "label"], {
        "sample": {f"s{i}": i for i in range(10)}, "label": {"g": 0},
    })
    bex = _form(x.reshape(-1, 1), ["sample", "feature"], {
        "sample": {f"s{i}": i for i in range(10)}, "feature": {"x": 0},
    })
    wtab = _form([[10, 20, 30, 40], [15, 25, 35, 45], [20, 30, 40, 50]],
                 ["stratum", "feature"], {
                     "stratum": {f"r{i}": i for i in range(3)},
                     "feature": {name: i for i, name in enumerate(["a", "b", "c", "d"])},
                 })
    return vex, vmeta, bex, wtab


def test_r_oracles_for_040(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    script = r'''
suppressPackageStartupMessages(library(DescTools))
x <- 1:10
g <- rep(1:2, each=5)
v <- VanWaerdenTest(x, g)
cat("VW", sprintf("%.17g", c(v$statistic, v$parameter, v$p.value)), "\n")
b <- BartelsRankTest(x)
cat("BART", sprintf("%.17g", c(b$statistic[1], b$statistic[2], b$mu, b$var, b$p.value)), "\n")
tab <- array(c(10,20,30,40, 15,25,35,45, 20,30,40,50), dim=c(2,2,3))
w <- WoolfTest(tab)
cat("WOOLF", sprintf("%.17g", c(w$statistic, w$parameter, w$p.value)), "\n")
'''
    proc = subprocess.run(["Rscript", "-e", script], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R DescTools not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"VW", "BART", "WOOLF"}:
            values[parts[0]] = [float(v) for v in parts[1:]]
    assert set(values) == {"VW", "BART", "WOOLF"}

    vex, vmeta, bex, wtab = _inputs()
    v, _ = _run(VanWaerdenStep(), {"group_label": "g", "group_a": "0", "group_b": "1"}, [vex, vmeta])
    assert v["statistic"] == pytest.approx(values["VW"][0], rel=1e-5)
    assert v["df"] == values["VW"][1]
    assert v["p"] == pytest.approx(values["VW"][2], rel=1e-5)

    b, _ = _run(BartelsRankStep(), {"value_label": "x"}, [bex])
    assert b["RVN"] == pytest.approx(values["BART"][0], rel=1e-5)
    assert b["z"] == pytest.approx(values["BART"][1], rel=1e-5)
    assert b["mu"] == pytest.approx(values["BART"][2], rel=1e-5)
    assert b["var"] == pytest.approx(values["BART"][3], rel=1e-5)
    assert b["p"] == pytest.approx(values["BART"][4], rel=1e-5)

    w, _ = _run(WoolfTestStep(), {}, [wtab])
    assert w["statistic"] == pytest.approx(values["WOOLF"][0], rel=1e-5)
    assert w["df"] == values["WOOLF"][1]
    assert w["p"] == pytest.approx(values["WOOLF"][2], rel=1e-5)
