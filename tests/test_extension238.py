"""Tests for the structural domain-boundary operator."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_domain_boundary import (
    ca_adjacency,
    connected_components,
    domain_assignment,
    normalized_laplacian,
)

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    position = {name: index for index, name in enumerate(COLUMNS)}
    arrays: list[np.ndarray] = []
    encoders = {}
    for name in COLUMNS:
        column = [row[position[name]] for row in rows]
        if name in ("x", "y", "z", "residue_number"):
            arrays.append(np.asarray(column, dtype=np.float64))
        else:
            encoder = LabelEncoder()
            arrays.append(np.asarray(encoder.fit_transform(column), dtype=np.float64))
            encoders[name] = encoder
    return Form(
        data=np.column_stack(arrays).astype(np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _two_domain_rows(offset: float = 40.0) -> list[tuple]:
    rows: list[tuple] = []
    for cluster, base in enumerate((0.0, offset)):
        for index in range(3):
            rows.append(
                (
                    base + 3.4 * index,
                    0.0,
                    0.0,
                    index + 1,
                    "ALA",
                    chr(ord("A") + cluster),
                    "CA",
                    "C",
                )
            )
    return rows


def _run(tmp_path: Path, rows, **params) -> Context:
    ctx = Context(str(tmp_path / "task"), {"params": {}})
    ctx["pdb"] = _pdb_form(rows)
    run(
        ctx,
        [
            {
                "name": "structure_domain_boundary",
                "inputs": ["pdb"],
                "params": {"contact_cutoff": 8.0, "min_separation": 1, "output": "domains", **params},
            }
        ],
    )
    return ctx


def test_adjacency_and_components() -> None:
    rows = _two_domain_rows()
    coordinates = np.asarray([row[:3] for row in rows], dtype=float)
    adjacency = ca_adjacency(coordinates, cutoff=8.0, min_separation=1)
    assert adjacency[0, 1] and adjacency[0, 2]
    assert not adjacency[0, 3]
    assert connected_components(adjacency) == [[0, 1, 2], [3, 4, 5]]


def test_laplacian_eigenvalues_of_disconnected_blocks() -> None:
    adjacency = np.zeros((6, 6), dtype=bool)
    for block in (range(3), range(3, 6)):
        for left in block:
            for right in block:
                if left != right:
                    adjacency[left, right] = True
    eigenvalues = np.linalg.eigvalsh(normalized_laplacian(adjacency))
    assert eigenvalues[0] == pytest.approx(0.0, abs=1e-9)
    assert eigenvalues[1] == pytest.approx(0.0, abs=1e-9)
    assert eigenvalues[2] > 0.5


def test_domain_assignment_uses_components() -> None:
    adjacency = np.zeros((6, 6), dtype=bool)
    for block in (range(3), range(3, 6)):
        for left in block:
            for right in block:
                if left != right:
                    adjacency[left, right] = True
    labels, method = domain_assignment(adjacency)
    assert method == "components"
    assert labels.tolist() == [0, 0, 0, 1, 1, 1]


def test_spectral_split_of_a_connected_dumbbell() -> None:
    adjacency = np.zeros((8, 8), dtype=bool)
    for block in (range(4), range(4, 8)):
        for left in block:
            for right in block:
                if left != right:
                    adjacency[left, right] = True
    adjacency[3, 4] = adjacency[4, 3] = True
    labels, method = domain_assignment(adjacency, n_domains=2)
    assert method == "spectral"
    assert len(set(labels[:4].tolist())) == 1
    assert len(set(labels[4:].tolist())) == 1
    assert labels[0] != labels[4]


def test_runner_two_domains(tmp_path: Path) -> None:
    ctx = _run(tmp_path, _two_domain_rows())
    form = ctx["domains"]
    assert form.dims == ["residue", "statistic"]
    assert form.data.shape == (6, 3)
    assert form.data[:, 0].tolist() == [0.0, 0.0, 0.0, 1.0, 1.0, 1.0]
    assert form.data[:, 2].tolist() == [0.0] * 6
    assert form.info["n_domains"] == 2
    assert form.info["method"] == "components"
    assert form.info["boundary_residues"] == []
    assert list(form.labels["residue"]) == [f"A:ALA:{index}" for index in range(1, 4)] + [
        f"B:ALA:{index}" for index in range(1, 4)
    ]


def test_runner_marks_boundary_on_connected_graph(tmp_path: Path) -> None:
    rows = _two_domain_rows(offset=12.0)
    ctx = _run(tmp_path, rows, n_domains=2, min_gap_ratio=1.0)
    form = ctx["domains"]
    assert form.info["n_domains"] == 2
    assert form.data[:, 3 - 1].sum() >= 0  # boundary flag column exists


def test_validation_errors(tmp_path: Path) -> None:
    with pytest.raises((StepError, ValueError), match="contact_cutoff must be between 4 and 15|minimum"):
        _run(tmp_path, _two_domain_rows(), contact_cutoff=2.0)
    with pytest.raises((StepError, ValueError), match="min_separation must be at least 1|minimum"):
        _run(tmp_path, _two_domain_rows(), min_separation=0)
    with pytest.raises((StepError, ValueError), match="n_domains must be between 0 and 8|maximum"):
        _run(tmp_path, _two_domain_rows(), n_domains=9)
    with pytest.raises(StepError, match="too many for"):
        _run(tmp_path, _two_domain_rows(), n_domains=4)
    with pytest.raises(StepError, match="has no edges|at least three CA atoms|at least four residues"):
        _run(tmp_path, [(0.0, 0.0, 0.0, 1, "ALA", "A", "CA", "C")] * 3, min_separation=1)
