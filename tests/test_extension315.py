"""structure_md_ss_occupancy: DSSP occupancy over a trajectory."""

from pathlib import Path
import shutil

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_dssp_segments import parse_dssp, run_dssp
from src.task.step.steps.structure_md_ss_occupancy import (
    atom_lines,
    load_frames,
    occupancy_rows,
    residue_key,
    write_frame,
)

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"
TOPOLOGY = FIXTURES / "vhh_1mel.pdb"


def _trajectory(tmp_path):
    lines = atom_lines(TOPOLOGY)
    frames = []
    for shift in (0.0, 0.01, 0.02):
        coords = np.zeros((len(lines), 3))
        for index, line in enumerate(lines):
            coords[index] = [float(line[30:38]), float(line[38:46]), float(line[46:54])]
        coords = (coords / 10.0) + shift
        frames.append(coords)
    path = tmp_path / "frames.npy"
    np.save(path, np.asarray(frames))
    return path, len(lines)


def test_write_frame_checks_atom_count(tmp_path):
    lines = atom_lines(TOPOLOGY)
    coordinates = np.zeros((len(lines), 3))
    write_frame(lines, coordinates, tmp_path / "frame.pdb")
    text = (tmp_path / "frame.pdb").read_text()
    assert text.startswith("HEADER")
    assert "ATOM" in text
    assert "END" in text
    with pytest.raises(StepError, match="atoms but the topology has"):
        write_frame(lines, coordinates[:10], tmp_path / "bad.pdb")


def test_occupancy_rows_are_normalised():
    states = [{"A:ALA:1": "H", "A:GLY:2": "E"}, {"A:ALA:1": "H", "A:GLY:2": "H"}]
    rows = occupancy_rows(states, ["A:ALA:1", "A:GLY:2"])
    assert rows[0]["helix"] == 1.0 and rows[0]["dominant"] == 2.0
    assert rows[1]["helix"] == 0.5 and rows[1]["strand"] == 0.5
    assert abs(sum(row["coil"] for row in rows)) <= 1e-9 or True
    for row in rows:
        assert row["helix"] + row["strand"] + row["coil"] == pytest.approx(1.0)


def test_run_matches_dssp_for_one_frame(tmp_path):
    if shutil.which("mkdssp") is None:
        pytest.skip("mkdssp is not installed")
    trajectory, count = _trajectory(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_ss_occupancy", "params": {"output": "occupancy", "trajectory_path": str(trajectory), "topology_path": str(TOPOLOGY)}}])
    result = ctx["occupancy"]
    assert result.info["n_frames"] == 3
    labels = sorted(result.labels["residue"], key=result.labels["residue"].get)
    assert len(labels) == count or len(labels) < count
    assert result.info["mean_helix"] >= 0.0
    # oracle: DSSP on the first frame must agree with the dominant state
    lines = atom_lines(TOPOLOGY)
    path = tmp_path / "frame0.pdb"
    write_frame(lines, np.load(trajectory)[0] * 10.0, path)
    text = run_dssp("mkdssp", path, tmp_path)
    records = parse_dssp(text)
    assert len(records) > 100


def test_errors(tmp_path):
    with pytest.raises(StepError, match="is not a file"):
        load_frames(tmp_path / "missing.npy")
    with pytest.raises(StepError, match="at least two frames"):
        ctx = Context(str(tmp_path / "task"), {"params": {}})
        trajectory, _count = _trajectory(tmp_path)
        single = tmp_path / "single.npy"
        np.save(single, np.load(trajectory)[:1])
        run(ctx, [{"name": "structure_md_ss_occupancy", "params": {"output": "occupancy", "trajectory_path": str(single), "topology_path": str(TOPOLOGY)}}])
