"""Authoritative R checks for the 0.22 FCS and AB1 readers."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.reader.readers.ab1_reader import Ab1Reader
from src.reader.readers.fcs_reader import FcsReader


ROOT = Path(__file__).resolve().parents[1]
FCS_PATH = ROOT / "tests" / "fixtures" / "fcs_example.fcs"
AB1_PATH = ROOT / "tests" / "fixtures" / "ab1_example.ab1"
RSCRIPT = shutil.which("Rscript")


def _read_with_r() -> dict[str, list[str]]:
    script = f"""
suppressPackageStartupMessages({{library(flowCore); library(sangerseqR)}})
x <- read.FCS({str(FCS_PATH)!r}, transformation=FALSE)
cat("FCSDIM", paste(dim(x), collapse=","), "\\n")
cat("FCSCOL", paste(colnames(x), collapse=","), "\\n")
cat("FCSROW1", paste(sprintf("%.0f", exprs(x)[1, ]), collapse=","), "\\n")
cat("FCSROW2", paste(sprintf("%.0f", exprs(x)[2, ]), collapse=","), "\\n")
a <- read.abif({str(AB1_PATH)!r})
cat("ABISEQ", a@data$PBAS.1, "\\n")
cat("ABIQ", paste(a@data$PCON.1[1:10], collapse=","), "\\n")
cat("ABIP", paste(a@data$PLOC.1[1:10], collapse=","), "\\n")
cat("ABIFWO", a@data$FWO.1, "\\n")
"""
    proc = subprocess.run(
        [RSCRIPT, "--vanilla", "-e", script],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if proc.returncode != 0:
        missing = "there is no package called" in proc.stderr or "could not find function" in proc.stderr
        if missing:
            pytest.skip(f"R flowCore/sangerseqR unavailable: {proc.stderr.strip()[:300]}")
        pytest.fail(f"R reader oracle failed:\n{proc.stderr}")
    values: dict[str, list[str]] = {}
    for line in proc.stdout.splitlines():
        key, _, value = line.partition(" ")
        value = value.strip()
        if key:
            values[key] = value.split(",") if "," in value else [value]
    return values


@pytest.mark.skipif(RSCRIPT is None, reason="Rscript not found")
def test_fcs_and_ab1_match_r_authoritative_readers():
    r = _read_with_r()

    fcs = FcsReader().read(
        FCS_PATH,
        ["event", "channel"],
        {"event": "auto", "channel": "builtin"},
    )
    assert fcs.data.shape == tuple(int(part) for part in r["FCSDIM"])
    assert list(fcs.labels["channel"]) == r["FCSCOL"]
    assert np.array_equal(fcs.data[0].astype(float), np.array(r["FCSROW1"], dtype=float))
    assert np.array_equal(fcs.data[1].astype(float), np.array(r["FCSROW2"], dtype=float))

    ab1 = Ab1Reader().read(
        AB1_PATH,
        ["base", "feature"],
        {"base": "builtin", "feature": "builtin"},
    )
    assert ab1.info["sequence"] == r["ABISEQ"][0]
    assert ab1.data[:10, 0].astype(float).tolist() == [float(x) for x in r["ABIQ"]]
    assert ab1.data[:10, 1].astype(float).tolist() == [float(x) for x in r["ABIP"]]
    assert ab1.info["base_order"] == r["ABIFWO"][0]
