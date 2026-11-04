"""End-to-end checks for the v1.43.0 operators through the task runner."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps._sequence_common import encode_sequences

COLUMNS = ("x", "y", "z", "residue_number", "resname", "chain", "atom_name", "element")


def _pdb_form(rows) -> Form:
    columns = list(zip(*rows))
    numerics = [np.asarray(columns[index], dtype=np.float64) for index in (0, 1, 2, 3)]
    encoders = {}
    encoded = {}
    for index, name in zip((4, 5, 6, 7), ("resname", "chain", "atom_name", "element")):
        encoder = LabelEncoder()
        encoded[name] = encoder.fit_transform(list(columns[index]))
        encoders[name] = encoder
    matrix = np.column_stack(
        [numerics[0], numerics[1], numerics[2], numerics[3],
         encoded["resname"], encoded["chain"], encoded["atom_name"], encoded["element"]]
    ).astype(np.float32)
    return Form(
        data=matrix,
        dims=["atom", "field"],
        labels={
            "atom": {f"atom:{index}": index for index in range(len(rows))},
            "field": {name: index for index, name in enumerate(COLUMNS)},
        },
        info={"missing_code": np.nan, "encoders": {"field": encoders}},
    )


def _hollow_cube(edge: float = 5.0, step: float = 1.5) -> Form:
    rows = []
    values = np.arange(-edge, edge + 1e-9, step)
    serial = 0
    for axis in range(3):
        for sign in (-1.0, 1.0):
            for first in values:
                for second in values:
                    coordinates = [0.0, 0.0, 0.0]
                    coordinates[axis] = sign * edge
                    coordinates[(axis + 1) % 3] = float(first)
                    coordinates[(axis + 2) % 3] = float(second)
                    serial += 1
                    rows.append((*coordinates, serial, "ALA", "A", "CA", "C"))
    return _pdb_form(rows)


def test_cavity_runner_round_trip(tmp_path: Path) -> None:
    ctx = Context(str(tmp_path / "cavity"), {"params": {}})
    ctx["pdb"] = _hollow_cube()
    run(
        ctx,
        [{"name": "structure_cavity_scan", "inputs": ["pdb"], "params": {"min_volume": 5.0, "output": "cavities"}}],
    )
    assert ctx["cavities"].data.shape[1] == 5
    exports = sorted((tmp_path / "cavity").rglob("*structure_cavity_scan*.json"))
    assert exports, "the runner must write the step export JSON"
    payload = json.loads(exports[-1].read_text(encoding="utf-8"))
    assert payload["n_cavities"] >= 1


def test_ligand_map_runner_round_trip(tmp_path: Path) -> None:
    rows = [
        (0.0, 0.0, 0.0, 1, "LIG", "A", "C1", "C"),
        (2.0, 0.0, 0.0, 1, "LIG", "A", "C2", "C"),
        (0.0, 0.0, 3.0, 1, "ALA", "A", "CA", "C"),
        (0.0, 0.0, 6.0, 2, "GLY", "A", "CA", "C"),
    ]
    ctx = Context(str(tmp_path / "ligand"), {"params": {}})
    ctx["pdb"] = _pdb_form(rows)
    run(
        ctx,
        [{"name": "structure_ligand_residue_map", "inputs": ["pdb"], "params": {"cutoff": 4.0, "output": "map"}}],
    )
    assert ctx["map"].data.shape == (2, 2)


def test_scaffold_tree_runner_round_trip(tmp_path: Path) -> None:
    pytest.importorskip("rdkit")
    ctx = Context(str(tmp_path / "scaffold"), {"params": {}})
    run(
        ctx,
        [
            {
                "name": "rdkit_scaffold_tree",
                "inputs": [],
                "params": {"smiles": "c1ccccc1 benzene\nCc1ccccc1 toluene", "max_level": 2, "output": "tree"},
            }
        ],
    )
    assert ctx["tree"].data.shape == (1, 4)


def test_repeat_runner_round_trip(tmp_path: Path) -> None:
    ctx = Context(str(tmp_path / "repeat"), {"params": {}})
    ctx["fasta"] = encode_sequences(["ATATAT"], "sequence", "position", "DNA")
    run(ctx, [{"name": "sequence_repeat_finder", "inputs": ["fasta"], "params": {"output": "repeats"}}])
    assert ctx["repeats"].data.tolist() == [[1.0, 2.0, 3.0, 6.0]]


def test_runner_rejects_undeclared_parameter(tmp_path: Path) -> None:
    ctx = Context(str(tmp_path / "bad"), {"params": {}})
    ctx["fasta"] = encode_sequences(["ATATAT"], "sequence", "position", "DNA")
    with pytest.raises((StepError, ValueError)):
        run(ctx, [{"name": "sequence_repeat_finder", "inputs": ["fasta"], "params": {"not_a_param": 1}}])
