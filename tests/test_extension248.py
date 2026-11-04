"""Tests for the docking pose clustering operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.vina_pose_cluster import (
    VinaPoseClusterStep,
    cluster_tables,
    pose_tables,
)

FIELDS = {"x": 0, "y": 1, "z": 2, "atomic_number": 3}


def _pose_form(poses) -> Form:
    frames = []
    pose_labels = {}
    atom_labels = {}
    for p_index, coordinates in enumerate(poses):
        pose_labels[f"pose{p_index}"] = p_index
        rows = []
        for a_index, (x, y, z, number) in enumerate(coordinates):
            atom_labels.setdefault(f"atom{a_index + 1}", a_index)
            rows.append([x, y, z, number])
        frames.append(np.asarray(rows, dtype=np.float32))
    data = np.stack(frames, axis=0)
    return Form(
        data,
        dims=["pose", "atom", "field"],
        labels={
            "pose": pose_labels,
            "atom": atom_labels,
            "field": dict(FIELDS),
        },
        info={"missing_code": np.nan},
    )


A = [(0.0, 0.0, 0.0, 6.0), (1.5, 0.0, 0.0, 6.0), (0.0, 1.5, 0.0, 8.0)]
B = [(0.0, 0.0, 0.0, 6.0), (2.6, 0.0, 0.0, 6.0), (0.0, 2.6, 0.0, 8.0)]


def _rotated_180() -> list[tuple[float, float, float, float]]:
    return [(-x, -y, z, number) for x, y, z, number in A]


def test_pose_tables_validation() -> None:
    form = _pose_form([A])
    tables = pose_tables(form, "pose", "atom", "field")
    assert len(tables) == 1
    assert tables[0]["n_atoms"] == 3
    with pytest.raises(StepError, match="no 'p' dimension"):
        pose_tables(form, "p", "atom", "field")


def test_cluster_tables() -> None:
    tables = pose_tables(_pose_form([A, B, _rotated_180()]), "pose", "atom", "field")
    rows, n_clusters = cluster_tables(tables, cutoff=0.5, allow_symmetry=True)
    assert n_clusters == 2
    assert [row["cluster"] for row in rows] == [1, 2, 1]
    assert rows[2]["distance"] == pytest.approx(0.0, abs=1e-4)
    assert rows[1]["distance"] == pytest.approx(0.0)

    merged, count = cluster_tables(tables, cutoff=10.0, allow_symmetry=True)
    assert count == 1
    assert [row["cluster"] for row in merged] == [1, 1, 1]


def test_symmetry_merges_swapped_atoms() -> None:
    first = [(0.0, 0.0, 0.0, 6.0), (1.4, 0.0, 0.0, 6.0)]
    second = [(1.4, 0.0, 0.0, 6.0), (0.0, 0.0, 0.0, 6.0)]
    tables = pose_tables(_pose_form([first, second]), "pose", "atom", "field")
    rows, count = cluster_tables(tables, cutoff=0.2, allow_symmetry=True)
    assert count == 1
    assert all(row["cluster"] == 1 for row in rows)


def test_run(tmp_path) -> None:
    form = _pose_form([A, B, _rotated_180()])
    params = {"output": "clusters", "cutoff": 0.5, "allow_symmetry": True}
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["poses"] = form
    run(ctx, [{"name": "vina_pose_cluster", "inputs": ["poses"], "params": params}])
    out = ctx["clusters"]
    assert out.dims == ["pose", "statistic"]
    assert out.data.shape == (3, 3)
    assert out.info["n_clusters"] == 2


def test_errors() -> None:
    tables = pose_tables(_pose_form([A]), "pose", "atom", "field")
    with pytest.raises(StepError, match="cutoff must be positive"):
        cluster_tables(tables, cutoff=0.0)
    assert VinaPoseClusterStep.definition["inputs_arity"] == 1
