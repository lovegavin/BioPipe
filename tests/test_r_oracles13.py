"""Authoritative R checks for the 0.28 flow-compensation and causality batch."""
from __future__ import annotations

import csv
import shutil
import subprocess

import numpy as np
import pytest

from src.core import Form
from src.task.step.steps.arch_test import ArchTestStep
from src.task.step.steps.flow_compensate import FlowCompensateStep
from src.task.step.steps.granger_causality import GrangerCausalityStep


RSCRIPT = shutil.which("Rscript")


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = params
        self.metadata = {}


def _form(data, dims, labels):
    form = Form(np.asarray(data, dtype=np.float64), list(dims), labels, {"missing_code": np.nan})
    form.validate()
    return form


def _labels(names):
    return {name: i for i, name in enumerate(names)}


def _write_csv(path, header, rows):
    with open(path, "w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def _r_values(tmp_path, cause, effect, arch, events, spillover):
    _write_csv(
        tmp_path / "granger.csv",
        ["time", "cause", "effect"],
        [[i + 1, repr(float(cause[i])), repr(float(effect[i]))] for i in range(len(cause))],
    )
    _write_csv(
        tmp_path / "arch.csv",
        ["time", "value"],
        [[i + 1, repr(float(value))] for i, value in enumerate(arch)],
    )
    _write_csv(
        tmp_path / "events.csv",
        ["A", "B", "C"],
        [[repr(float(value)) for value in row] for row in events],
    )
    _write_csv(
        tmp_path / "spillover.csv",
        ["", "A", "B"],
        [["A", "1.0", "0.2"], ["B", "0.1", "1.0"]],
    )
    script = tmp_path / "oracle.R"
    script.write_text(
        f"""
suppressPackageStartupMessages({{library(lmtest); library(FinTS); library(flowCore)}})
d <- read.csv("{tmp_path.as_posix()}/granger.csv")
for (k in 1:3) {{
  r <- grangertest(effect ~ cause, order = k, data = d)
  cat("GRANGER", k, sprintf("%.10f", unname(r[[3]][2])), sprintf("%.10f", unname(r[[4]][2])),
      unname(r[[1]][1]), unname(r[[2]][2]), "\\n")
}}
a <- read.csv("{tmp_path.as_posix()}/arch.csv")
ar <- ArchTest(a[["value"]], lags = 5)
cat("ARCH", sprintf("%.10f", unname(ar[["statistic"]])),
    sprintf("%.10f", unname(ar[["p.value"]])), "\\n")
e <- as.matrix(read.csv("{tmp_path.as_posix()}/events.csv", check.names = FALSE))
sp <- as.matrix(read.csv("{tmp_path.as_posix()}/spillover.csv", row.names = 1, check.names = FALSE))
out <- exprs(compensate(flowFrame(e), sp))
for (i in seq_len(nrow(out))) {{
  cat("FLOW", sprintf("%.10f", as.numeric(out[i, ])), "\\n")
}}
"""
    )
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", str(script)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        if "there is no package called" in proc.stderr:
            pytest.skip(f"R oracle package unavailable: {proc.stderr.strip()[:300]}")
        pytest.fail(f"R 0.28 oracle failed:\n{proc.stderr}")
    values = {"GRANGER": [], "FLOW": []}
    for line in proc.stdout.splitlines():
        parts = line.split()
        if not parts:
            continue
        if parts[0] == "GRANGER":
            values["GRANGER"].append([float(parts[1])] + [float(value) for value in parts[2:]])
        elif parts[0] == "ARCH":
            values["ARCH"] = [float(parts[1]), float(parts[2])]
        elif parts[0] == "FLOW":
            values["FLOW"].append([float(value) for value in parts[1:]])
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_flow_causality_and_arch_match_r(tmp_path):
    rng = np.random.default_rng(11)
    n = 90
    cause = rng.normal(size=n)
    effect = np.zeros(n)
    for i in range(1, n):
        effect[i] = 0.5 * effect[i - 1] + 0.7 * cause[i - 1] + 0.3 * rng.normal()

    rng = np.random.default_rng(5)
    arch = rng.normal(size=100) * (1.0 + 0.6 * np.sin(np.arange(100) / 4.0))
    events = np.array([[1.0, 0.2, 5.0], [2.0, 0.5, 6.0], [3.0, 0.1, 7.0]])
    spillover = np.array([[1.0, 0.2], [0.1, 1.0]])
    r = _r_values(tmp_path, cause, effect, arch, events, spillover)

    series = _form(
        np.column_stack([cause, effect]),
        ["sample", "feature"],
        {"sample": _labels([f"t{i}" for i in range(n)]),
         "feature": {"cause": 0, "effect": 1}},
    )
    ctx = Ctx({"cause_label": "cause", "effect_label": "effect", "max_lag": 3})
    step = GrangerCausalityStep()
    step.run(ctx, [series])
    export = step.export(ctx)
    for row, expected in zip(export["F"], r["GRANGER"]):
        assert row == pytest.approx(expected[1], abs=1e-5)
    for row, expected in zip(export["p"], r["GRANGER"]):
        assert row == pytest.approx(expected[2], abs=1e-9)
    for row, expected in zip(ctx["granger_causality"].data, r["GRANGER"]):
        assert row[2] == pytest.approx(expected[3], abs=1e-9)
        assert row[3] == pytest.approx(abs(expected[4]), abs=1e-9)

    arch_form = _form(
        arch.reshape(-1, 1),
        ["sample", "feature"],
        {"sample": _labels([f"t{i}" for i in range(len(arch))]), "feature": {"value": 0}},
    )
    ctx = Ctx({"value_label": "value", "lags": 5})
    step = ArchTestStep()
    step.run(ctx, [arch_form])
    assert step.export(ctx)["lm_statistic"] == pytest.approx(r["ARCH"][0], abs=1e-5)
    assert step.export(ctx)["lm_p"] == pytest.approx(r["ARCH"][1], abs=1e-9)

    event_form = _form(
        events,
        ["event", "channel"],
        {"event": _labels(["e0", "e1", "e2"]),
         "channel": {"A": 0, "B": 1, "C": 2}},
    )
    spill_form = _form(
        spillover,
        ["detector", "fluorochrome"],
        {"detector": _labels(["A", "B"]), "fluorochrome": _labels(["A", "B"])},
    )
    ctx = Ctx({})
    step = FlowCompensateStep()
    step.run(ctx, [event_form, spill_form])
    assert np.allclose(ctx["flow_compensate"].data, np.asarray(r["FLOW"]), atol=2e-5)
