"""Tests for structure_ligand_burial and the runner-level contracts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from src.core.errors import StepError
from src.core.forms.form import Form
from src.reader.readers._encoder import LabelEncoder
from src.task.context.base import Context
from src.task.runner import run
from src.task.step.steps.structure_ligand_burial import (
    StructureLigandBurialStep,
    ligand_groups,
)

FIELD_NAMES = (
    "x",
    "y",
    "z",
    "occupancy",
    "bfactor",
    "residue_number",
    "chain",
    "resname",
    "element",
    "atom_name",
    "altloc",
    "insertion_code",
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form(atoms):
    columns = {
        "chain": [atom.get("chain", "A") for atom in atoms],
        "resname": [atom.get("resname", "ALA") for atom in atoms],
        "element": [atom.get("element", "C") for atom in atoms],
        "atom_name": [atom["atom_name"] for atom in atoms],
        "altloc": [" " for _ in atoms],
        "insertion_code": [" " for _ in atoms],
    }
    encoders = {name: LabelEncoder() for name in columns}
    codes = {
        name: encoders[name].fit_transform(values)
        for name, values in columns.items()
    }
    matrix = []
    for index, atom in enumerate(atoms):
        matrix.append(
            [
                atom["x"],
                atom["y"],
                atom["z"],
                atom.get("occupancy", 1.0),
                atom.get("bfactor", 0.0),
                atom["number"],
                codes["chain"][index],
                codes["resname"][index],
                codes["element"][index],
                codes["atom_name"][index],
                codes["altloc"][index],
                codes["insertion_code"][index],
            ]
        )
    return Form(
        data=np.asarray(matrix, dtype=np.float32),
        dims=["atom", "field"],
        labels={
            "atom": {f"atom{i}": i for i in range(len(matrix))},
            "field": {name: position for position, name in enumerate(FIELD_NAMES)},
        },
        info={
            "missing_code": np.nan,
            "encoders": {"field": encoders},
        },
    )


def _protein_shell(center=(0.0, 0.0, 0.0), radius=4.5):
    atoms = []
    offsets = [
        (radius, 0.0, 0.0),
        (-radius, 0.0, 0.0),
        (0.0, radius, 0.0),
        (0.0, -radius, 0.0),
        (0.0, 0.0, radius),
        (0.0, 0.0, -radius),
    ]
    for index, offset in enumerate(offsets):
        atoms.append(
            {
                "atom_name": "CA",
                "element": "C",
                "resname": "ALA",
                "number": index + 1,
                "chain": "A",
                "x": center[0] + offset[0],
                "y": center[1] + offset[1],
                "z": center[2] + offset[2],
            }
        )
    return atoms


def test_buried_ligand_in_shell() -> None:
    atoms = _protein_shell() + [
        {
            "atom_name": "C1",
            "element": "C",
            "resname": "LIG",
            "number": 1,
            "chain": "A",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }
    ]
    form = _form(atoms)
    ctx = Ctx({})
    step = StructureLigandBurialStep()
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.dims == ["ligand", "statistic"]
    assert out.data.shape == (1, 4)
    assert out.data[0, 3] > 0.5


def test_exposed_ligand_far_from_protein() -> None:
    atoms = _protein_shell() + [
        {
            "atom_name": "C1",
            "element": "C",
            "resname": "LIG",
            "number": 1,
            "chain": "A",
            "x": 40.0,
            "y": 0.0,
            "z": 0.0,
        }
    ]
    form = _form(atoms)
    ctx = Ctx({})
    step = StructureLigandBurialStep()
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data[0, 3] < 0.05


def test_groups_and_errors() -> None:
    atoms = _protein_shell() + [
        {
            "atom_name": "C1",
            "element": "C",
            "resname": "LIG",
            "number": 1,
            "chain": "A",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        },
        {
            "atom_name": "C2",
            "element": "C",
            "resname": "LIG",
            "number": 1,
            "chain": "A",
            "x": 1.0,
            "y": 0.0,
            "z": 0.0,
        },
    ]
    form = _form(atoms)
    groups, protein_coords, protein_radii = ligand_groups(form, "atom", "field", ["LIG"], [])
    assert len(groups) == 1
    assert groups[0]["label"] == "A:LIG:1"
    assert len(protein_coords) == 6
    with pytest.raises(StepError, match="no ligand residue matches"):
        ctx = Ctx({"ligand_resnames": "HEM"})
        StructureLigandBurialStep().run(ctx, [form])
    with pytest.raises(StepError, match="probe_radius"):
        ctx = Ctx({"probe_radius": 0.5})
        StructureLigandBurialStep().run(ctx, [form])
    with pytest.raises(StepError, match="n_points"):
        ctx = Ctx({"n_points": 8})
        StructureLigandBurialStep().run(ctx, [form])
    with pytest.raises(StepError, match="no protein atoms"):
        only_ligand = _form(atoms[-2:])
        ctx = Ctx({})
        StructureLigandBurialStep().run(ctx, [only_ligand])


def test_runner_level_contracts(tmp_path: Path) -> None:
    atoms = _protein_shell() + [
        {
            "atom_name": "CA",
            "element": "C",
            "resname": "LIG",
            "number": 1,
            "chain": "A",
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
        }
    ]
    form = _form(atoms)
    work = tmp_path / "task"
    ctx = Context(work, {"params": {}})
    ctx["data"] = form
    run(
        ctx,
        [
            {"name": "structure_ligand_burial", "inputs": ["data"], "params": {"output": "burial"}},
        ],
    )
    assert ctx["burial"].data.shape == (1, 4)
    assert (work / "output" / "steps" / "01_structure_ligand_burial.json").is_file()
