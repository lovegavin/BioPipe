"""structure_md_sasa_occupancy: per-residue SASA statistics from Shrake-Rupley."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_sasa_occupancy import (
    load_frames,
    residue_sasa,
    sasa_rows,
)


def _atom_line(serial, name, resname, chain, number, x, y, z, element):
    return f"ATOM  {serial:5d} {name:<4s} {resname:>3s} {chain}{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"


def _single_atom(tmp_path):
    topology = tmp_path / "one.pdb"
    topology.write_text(_atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C") + "\n")
    frames = np.zeros((2, 1, 3))
    npy = tmp_path / "frames.npy"
    np.save(npy, frames / 10.0)
    return topology, npy


def test_single_atom_sasa_analytic(tmp_path):
    topology, npy = _single_atom(tmp_path)
    values, labels = residue_sasa(topology, np.load(npy) * 10.0, n_sphere_points=512)
    expected = 4 * np.pi * (1.7 + 1.4) ** 2
    assert labels == ["A:ALA:1"]
    assert values[0, 0] == pytest.approx(expected, rel=0.01)


def test_buried_atom_has_less_sasa(tmp_path):
    lines = [
        _atom_line(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
        _atom_line(2, "CA", "GLY", "B", 2, 2.4, 0.0, 0.0, "C"),
    ]
    topology = tmp_path / "two.pdb"
    topology.write_text("\n".join(lines) + "\n")
    coords = np.asarray([[[0, 0, 0], [2.4, 0, 0]]], dtype=float) / 10.0
    values, labels = residue_sasa(topology, coords * 10.0, n_sphere_points=512)
    isolated = 4 * np.pi * (3.1) ** 2
    assert values[0, 0] < isolated
    assert values[0, 1] < isolated


def test_rows_statistics():
    values = np.asarray([[10.0, 0.0], [20.0, 0.0], [30.0, 0.0]])
    rows = sasa_rows(values, ["A", "B"], exposed_threshold=15.0)
    assert rows[0]["residue"] == "B"
    assert rows[0]["mean_sasa"] == 0.0
    assert rows[1]["mean_sasa"] == pytest.approx(20.0)
    assert rows[1]["exposed_fraction"] == pytest.approx(2 / 3)


def test_run_writes_table(tmp_path):
    topology, npy = _single_atom(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_sasa_occupancy", "params": {"output": "sasa", "trajectory_path": str(npy), "topology_path": str(topology), "n_sphere_points": 512}}])
    table = ctx["sasa"]
    assert table.data.shape == (1, 4)
    assert table.info["n_frames"] == 2
    assert table.labels["residue"]["A:ALA:1"] == 0


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    with pytest.raises(StepError, match="atoms but the topology has"):
        topology, npy = _single_atom(tmp_path)
        residue_sasa(topology, np.zeros((2, 3, 3)))
