"""structure_md_hbond_lifetime: residence statistics."""

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps.structure_md_hbond_lifetime import lifetime_rows, run_lengths


def _atom(chain, resname, number, name, element):
    return {"chain": chain, "resname": resname, "number": number, "name": name, "element": element}


def test_run_lengths():
    assert run_lengths(np.array([True, True, False, True, True, True, False, True])) == [2, 3, 1]
    assert run_lengths(np.zeros(4, dtype=bool)) == []


def test_lifetime_rows_hand_case():
    atoms = [_atom("A", "SER", 1, "OG", "O"), _atom("A", "SER", 1, "HG", "H"), _atom("A", "ASP", 2, "OD1", "O")]
    triples = [(0, 1, 2)]
    presence = np.zeros((1, 10), dtype=bool)
    presence[0, :4] = True
    presence[0, 6:] = True
    distances = np.full((1, 10), 2.8)
    rows = lifetime_rows(atoms, triples, presence, distances, frame_time_ps=0.5, min_occupancy=0.5)
    assert len(rows) == 1
    row = rows[0]
    assert row["occupancy"] == pytest.approx(0.8)
    assert row["mean_lifetime_frames"] == pytest.approx((4 + 4) / 2)
    assert row["max_run_frames"] == 4
    assert row["transitions"] == 1
    assert row["mean_lifetime_ps"] == pytest.approx(2.0)
    low = lifetime_rows(atoms, triples, presence, distances, frame_time_ps=0.5, min_occupancy=0.9)
    assert low == []


def test_run_round_trip(tmp_path):
    from src.task.context import Context
    from src.task.runner import run

    head = "ATOM  {serial:5d} {name:<4s} {resname:>3s} A{number:4d}    {x:8.3f}{y:8.3f}{z:8.3f}  1.00  0.00          {element:>2s}"
    lines = [
        head.format(serial=1, name="OG", resname="SER", number=1, x=0.0, y=0.0, z=0.0, element="O"),
        head.format(serial=2, name="HG", resname="SER", number=1, x=1.0, y=0.0, z=0.0, element="H"),
        head.format(serial=3, name="OD1", resname="ASP", number=2, x=3.0, y=0.0, z=0.0, element="O"),
    ]
    topology = tmp_path / "top.pdb"
    topology.write_text("".join(line.ljust(80) + "\n" for line in lines))
    base = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [3.0, 0.0, 0.0]])
    frames = np.asarray([base] * 6)
    path = tmp_path / "traj.npy"
    np.save(path, frames / 10.0)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_hbond_lifetime", "params": {"trajectory_path": str(path), "topology_path": str(topology), "frame_time_ps": 0.5, "min_occupancy": 0.5}}])
    result = ctx["lifetimes"]
    assert result.data.shape == (1, 5)
    assert result.data[0, 0] == pytest.approx(1.0)
    assert result.info["max_lifetime_ps"] == pytest.approx(3.0)
    assert result.info["n_frames"] == 6
