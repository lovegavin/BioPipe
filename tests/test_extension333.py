"""structure_md_conformational_clusters: average-linkage RMSD clustering."""

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.context import Context
from src.task.runner import run
from src.task.step.steps.structure_md_conformational_clusters import cluster_frames, pairwise_rmsd

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures"


def _trajectory(tmp_path, groups=3, per_group=10, noise=0.2, seed=2):
    lines = [line for line in (FIXTURES / "vhh_1mel.pdb").read_text().splitlines() if line.startswith("ATOM") and line[21].strip() == "A"]
    topology = tmp_path / "top.pdb"
    topology.write_text("\n".join(lines) + "\nEND\n")
    base = np.array([[float(line[30:38]), float(line[38:46]), float(line[46:54])] for line in lines])
    rng = np.random.default_rng(seed)
    frames = []
    for group in range(groups):
        moved = base.copy()
        moved[len(base) // 2:] += np.array([0.0, 0.0, 4.0 * group])
        for _ in range(per_group):
            frames.append(moved + rng.normal(0.0, noise, moved.shape))
    path = tmp_path / "traj.npy"
    np.save(path, np.asarray(frames) / 10.0)
    return path, topology, len(frames)


def test_three_groups_cluster_separately(tmp_path):
    path, topology, count = _trajectory(tmp_path)
    from src.task.step.steps.structure_md_pca import ca_indices, kabsch, load_frames

    selected = kabsch(load_frames(path)[:, ca_indices(topology, 973), :])
    matrix = pairwise_rmsd(selected)
    labels, n_clusters = cluster_frames(matrix, 1.0)
    assert n_clusters == 3
    assert count == len(labels)


def test_identical_frames_single_cluster(tmp_path):
    path, topology, count = _trajectory(tmp_path, groups=1, per_group=5, noise=0.01)
    from src.task.step.steps.structure_md_pca import ca_indices, kabsch, load_frames

    selected = kabsch(load_frames(path)[:, ca_indices(topology, 973), :])
    labels, n_clusters = cluster_frames(pairwise_rmsd(selected), 1.0)
    assert n_clusters == 1


def test_run_and_errors(tmp_path):
    path, topology, count = _trajectory(tmp_path)
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    run(ctx, [{"name": "structure_md_conformational_clusters", "params": {"trajectory_path": str(path), "topology_path": str(topology), "cutoff": 1.0}}])
    result = ctx["clusters"]
    assert result.data.shape[0] == count
    assert sum(result.info["cluster_sizes"]) == count
    assert result.info["n_clusters"] >= 1
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "structure_md_conformational_clusters", "params": {"trajectory_path": str(path), "topology_path": str(topology), "cutoff": 0.0}}])
