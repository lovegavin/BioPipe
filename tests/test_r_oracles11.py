"""Authoritative flowCore checks for the 0.26 flow operators."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from src.reader.readers.fcs_reader import FcsReader
from src.task.step.steps.flow_gate import FlowGateStep
from src.task.step.steps.flow_transform import FlowTransformStep


RSCRIPT = shutil.which("Rscript")
FIXTURES = Path(__file__).resolve().parent / "fixtures"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params


def _form():
    return FcsReader().read(
        FIXTURES / "fcs_example.fcs",
        ["event", "channel"],
        {"event": "auto", "channel": "builtin"},
    )


def _r_values():
    script = """
suppressPackageStartupMessages(library(flowCore))
ff <- read.FCS("tests/fixtures/fcs_example.fcs", transformation=FALSE)
tf <- transform(ff, transformList(c("FSC-H","FL1-H"), arcsinhTransform(a=0,b=1,c=5)))
cat("TRANS", sprintf("%.10f", as.numeric(exprs(tf)[1:2, c("FSC-H","FL1-H")])), "\\n")
gate <- rectangleGate(filterId="g", list("FSC-H"=c(100,500), "SSC-H"=c(50,400)))
s <- summary(filter(ff, gate))
cat("GATE", s@true, s@count, sprintf("%.10f", s@p), "\\n")
"""
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        pytest.fail(f"R flowCore oracle failed:\n{proc.stderr}")
    values = {}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "TRANS":
            values["TRANS"] = [float(x) for x in parts[1:]]
        elif parts[0] == "GATE":
            values["GATE"] = [float(x) for x in parts[1:]]
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_flow_transform_and_gate_match_flowcore():
    values = _r_values()
    form = _form()

    ctx = Ctx({"channels": ["FSC-H", "FL1-H"], "a": 0.0, "b": 1.0, "c": 5.0})
    transform = FlowTransformStep()
    transform.run(ctx, [form])
    out = ctx["flow_transform"]
    assert out.data[0, 0] == pytest.approx(values["TRANS"][0], abs=2e-5)
    assert out.data[0, 2] == pytest.approx(values["TRANS"][2], abs=2e-5)
    assert out.data[1, 0] == pytest.approx(values["TRANS"][1], abs=2e-5)
    assert out.data[1, 2] == pytest.approx(values["TRANS"][3], abs=2e-5)

    ctx = Ctx({
        "x_channel": "FSC-H",
        "y_channel": "SSC-H",
        "x_min": 100.0,
        "x_max": 500.0,
        "y_min": 50.0,
        "y_max": 400.0,
    })
    gate = FlowGateStep()
    gate.run(ctx, [form])
    out = gate.export(ctx)
    assert out["n_inside"] == int(values["GATE"][0])
    assert out["n_total"] == int(values["GATE"][1])
    assert out["proportion"] == pytest.approx(values["GATE"][2], abs=1e-10)
