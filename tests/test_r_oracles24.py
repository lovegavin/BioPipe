"""R oracle checks for 0.39 Hotelling T2, Yuen and G-test."""
from __future__ import annotations

import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.g_test import GTestStep
from src.task.step.steps.hotelling_t2 import HotellingT2Step
from src.task.step.steps.yuen_test import YuenTestStep


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


def _forms():
    data = np.asarray([
        [1.0, 2.0, 3.0], [2.0, 1.5, 2.5], [1.5, 2.5, 3.5], [2.5, 2.0, 2.0],
        [3.0, 3.5, 4.0], [3.5, 3.0, 4.5], [4.0, 4.0, 3.5], [2.8, 3.2, 4.2],
    ])
    expr = _form(data.T, ["feature", "sample"], {
        "feature": {f"f{i}": i for i in range(3)},
        "sample": {f"s{i}": i for i in range(8)},
    })
    meta = _form([[0]] * 4 + [[1]] * 4, ["sample", "group"], {
        "sample": {f"s{i}": i for i in range(8)}, "group": {"g": 0},
    })
    a = [1, 2, 3, 4, 5, 6, 7, 8, 9, 100]
    b = [2, 3, 4, 5, 6, 7, 8, 9, 10, 11]
    yexpr = _form([a + b], ["feature", "sample"], {
        "feature": {"x": 0}, "sample": {f"s{i}": i for i in range(20)},
    })
    ymeta = _form([[0]] * 10 + [[1]] * 10, ["sample", "group"], {
        "sample": {f"s{i}": i for i in range(20)}, "group": {"g": 0},
    })
    table = _form([[10, 20, 30], [20, 15, 25], [30, 25, 20]], ["row", "column"], {
        "row": {f"r{i}": i for i in range(3)}, "column": {f"c{i}": i for i in range(3)},
    })
    return expr, meta, yexpr, ymeta, table


def test_r_oracles_for_039(tmp_path):
    if shutil.which("Rscript") is None:
        pytest.skip("Rscript not available")
    expr, meta, yexpr, ymeta, table = _forms()
    np.savetxt(tmp_path / "hot.csv", np.asarray([[1.0,2.0,3.0], [2.0,1.5,2.5], [1.5,2.5,3.5], [2.5,2.0,2.0], [3.0,3.5,4.0], [3.5,3.0,4.5], [4.0,4.0,3.5], [2.8,3.2,4.2]]), delimiter=",")
    np.savetxt(tmp_path / "yuen.csv", np.asarray([yexpr.data[0], yexpr.data[0]]), delimiter=",")
    # separate arrays
    a = np.asarray([1,2,3,4,5,6,7,8,9,100], dtype=float)
    b = np.asarray([2,3,4,5,6,7,8,9,10,11], dtype=float)
    np.savetxt(tmp_path / "a.csv", a, delimiter=",")
    np.savetxt(tmp_path / "b.csv", b, delimiter=",")
    np.savetxt(tmp_path / "table.csv", np.asarray(table.data), delimiter=",")
    script = r'''
suppressPackageStartupMessages(library(DescTools))
d <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "hot.csv"), header=FALSE))
h <- HotellingsT2Test(d[1:4,,drop=FALSE], d[5:8,,drop=FALSE])
cat("HOT", sprintf("%.17g", c(h$statistic, h$parameter[1], h$parameter[2], h$p.value)), "\n")
a <- scan(file.path(commandArgs(TRUE)[1], "a.csv"), quiet=TRUE)
b <- scan(file.path(commandArgs(TRUE)[1], "b.csv"), quiet=TRUE)
y <- YuenTTest(a, b, trim=0.2)
cat("YUEN", sprintf("%.17g", c(y$statistic, y$parameter[1], y$p.value, y$conf.int[1], y$conf.int[2], y$estimate[1], y$estimate[2])), "\n")
m <- as.matrix(read.csv(file.path(commandArgs(TRUE)[1], "table.csv"), header=FALSE))
g <- GTest(m, correct="none")
cat("G", sprintf("%.17g", c(g$statistic, g$parameter, g$p.value)), "\n")
'''
    proc = subprocess.run(["Rscript", "-e", script, str(tmp_path)], text=True, capture_output=True, check=False)
    if proc.returncode != 0:
        if "there is no package" in proc.stderr:
            pytest.skip("R DescTools not installed")
        pytest.fail(f"R failed: {proc.stderr}\n{proc.stdout}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if parts and parts[0] in {"HOT", "YUEN", "G"}:
            values[parts[0]] = [float(v) for v in parts[1:]]
    assert set(values) == {"HOT", "YUEN", "G"}

    h, _ = _run(HotellingT2Step(), {"group_label": "g", "group_a": "0", "group_b": "1"}, [expr, meta])
    assert h["F"] == pytest.approx(values["HOT"][0], rel=1e-5)
    assert h["df1"] == values["HOT"][1]
    assert h["df2"] == values["HOT"][2]
    assert h["p"] == pytest.approx(values["HOT"][3], rel=1e-5)

    _y, yform = _run(YuenTestStep(), {"group_label": "g", "group_a": "0", "group_b": "1"}, [yexpr, ymeta])
    row = yform.data[0]
    assert row[1] == pytest.approx(values["YUEN"][0], rel=1e-5)
    assert row[2] == pytest.approx(values["YUEN"][1], rel=1e-5)
    assert row[3] == pytest.approx(values["YUEN"][2], rel=1e-5)
    assert row[4] == pytest.approx(values["YUEN"][3], rel=1e-5)
    assert row[5] == pytest.approx(values["YUEN"][4], rel=1e-5)

    g, _ = _run(GTestStep(), {}, [table])
    assert g["G"] == pytest.approx(values["G"][0], rel=1e-5)
    assert g["df"] == values["G"][1]
    assert g["p"] == pytest.approx(values["G"][2], rel=1e-5)
