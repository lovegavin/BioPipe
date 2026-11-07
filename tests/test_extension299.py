"""structure_openmm_md_stability: drift statistics and a gated real trajectory."""

import os
import shutil
from pathlib import Path

import numpy as np
import pytest

from src.core.forms import Form
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_openmm_md_stability import (
    drift_rows,
    drift_summary,
    radius_of_gyration,
    temperature_from_kinetic,
)
from src.reader import read_source

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "vhh_1mel.pdb"


def test_temperature_and_radius_of_gyration():
    assert temperature_from_kinetic(0.0, 100) == 0.0
    assert temperature_from_kinetic(1.0 * 100 * 0.008314462618 / 2.0, 100) == pytest.approx(1.0, rel=1e-9)
    positions = np.array([[1.0, 0.0, 0.0], [-1.0, 0.0, 0.0]])
    assert radius_of_gyration(positions) == pytest.approx(1.0, rel=1e-9)


def test_drift_rows_and_summary():
    frames = [
        {"time_ps": 0.0, "temperature_k": 300.0, "potential_energy_kj": -1000.0, "rmsd_angstrom": 0.0, "radius_of_gyration_angstrom": 10.0},
        {"time_ps": 1.0, "temperature_k": 310.0, "potential_energy_kj": -990.0, "rmsd_angstrom": 1.5, "radius_of_gyration_angstrom": 10.5},
    ]
    rows = drift_rows(frames)
    assert [row["time_ps"] for row in rows] == [0.0, 1.0]
    summary = drift_summary(rows, seed=7)
    assert summary["mean_temperature_k"] == pytest.approx(305.0)
    assert summary["rmsd_final_angstrom"] == pytest.approx(1.5)
    assert summary["rg_change_angstrom"] == pytest.approx(0.5)
    assert summary["seed"] == 7


def _form():
    import tempfile

    lines = [line.rstrip() for line in FIXTURE.read_text().splitlines() if line.startswith("ATOM") and line[21] == "A" and line[17:20].strip() != "HOH"]
    path = Path(tempfile.mkdtemp()) / "chainA.pdb"
    path.write_text("\n".join(lines) + "\nTER\nEND\n")
    return read_source(str(path), ["atom", "field"], {"atom": "auto", "field": "builtin"})


def test_run_requires_openmm():
    ctx = Context("/tmp/operon_md_299", {"params": {}})
    ctx["pdb"] = _form()
    if shutil.which("pdbfixer") is None and not pytest.importorskip("openmm", reason="openmm is not installed"):
        return
    run(ctx, [{"name": "structure_openmm_md_stability", "inputs": ["pdb"], "params": {"output": "frames", "steps": 10, "sample_every": 5, "minimize_iterations": 10}}])
    result = ctx["frames"]
    assert result.dims == ["frame", "statistic"]
    assert result.data.shape == (3, 5)


@pytest.mark.skipif(os.environ.get("OPERON_OPENMM_REAL") != "1", reason="set OPERON_OPENMM_REAL=1 for a real trajectory")
def test_real_trajectory():
    pytest.importorskip("openmm")
    ctx = Context("/tmp/operon_md_299_real", {"params": {}})
    ctx["pdb"] = _form()
    run(ctx, [{"name": "structure_openmm_md_stability", "inputs": ["pdb"], "params": {"output": "frames", "steps": 200, "sample_every": 50, "temperature": 300.0, "seed": 3, "minimize_iterations": 200}}])
    result = ctx["frames"]
    temperatures = result.data[:, 1]
    assert 200.0 < temperatures.mean() < 420.0
    assert result.info["rmsd_final_angstrom"] < 3.0
    assert np.all(np.isfinite(result.data))
