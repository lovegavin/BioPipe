"""Tests for amide-pi, cation-pi and aromatic stacking operators."""
from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader import read_source
from src.task.context.base import Context
from src.task.step.steps._protein_common import decode_column
from src.task.step.steps._ring_geometry import (
    amide_groups,
    angle_between,
    cation_centroids,
    ring_planes,
)
from src.task.step.steps._structure_common import atom_coords, residue_numbers
from src.task.step.steps.structure_amide_pi_bonds import (
    StructureAmidePiBondsStep,
    amide_pi_bonds,
)
from src.task.step.steps.structure_aromatic_stacking import (
    StructureAromaticStackingStep,
)
from src.task.step.steps.structure_cation_pi import (
    StructureCationPiStep,
    cation_pi_bonds,
)


class Ctx(dict):
    def __init__(self, params: dict):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(record, serial, name, resname, chain, number, x, y, z, element, altloc=" ", icode=" "):
    return (
        f"{record:<6}{serial:>5} {name:<4}{altloc}{resname:>3} "
        f"{chain}{number:>4}{icode}   "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{0.00:>6.2f}          {element:>2}"
    )


def _hexagon(start_serial, resname, chain, number, center, radius=1.4):
    names = ["CG", "CD1", "CE1", "CZ", "CE2", "CD2"]
    center = np.asarray(center, dtype=float)
    rows = []
    for index, name in enumerate(names):
        theta = math.radians(60.0 * index)
        point = center + np.array([radius * math.cos(theta), radius * math.sin(theta), 0.0])
        rows.append(_atom("ATOM", start_serial + index, name, resname, chain, number, *point, "C"))
    return rows


def _write(path, lines):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _form(path):
    return read_source(
        path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _fields(form):
    resnames = decode_column(form, "field", "resname")
    atom_names = decode_column(form, "field", "atom_name")
    chains = decode_column(form, "field", "chain")
    numbers = residue_numbers(form, "field")
    labels = np.array(
        [
            f"{chain}:{resname}:{number}"
            for chain, resname, number in zip(chains, resnames, numbers)
        ]
    )
    return atom_coords(form, "field"), resnames, atom_names, chains, numbers, labels


def _amide_fixture(tmp_path) -> Path:
    lines = [
        _atom("ATOM", 1, "N", "ALA", "A", 1, 0.0, 0.0, 1.6, "N"),
        _atom("ATOM", 2, "CA", "ALA", "A", 1, 0.0, 0.0, 2.0, "C"),
        _atom("ATOM", 3, "C", "ALA", "A", 1, 0.0, 0.0, 2.4, "C"),
        _atom("ATOM", 4, "O", "ALA", "A", 1, 0.0, 0.0, 3.2, "O"),
        _atom("ATOM", 5, "N", "PHE", "A", 2, 0.0, 0.0, 2.0, "N"),
        _atom("ATOM", 6, "CA", "PHE", "A", 2, 0.0, 0.0, 3.0, "C"),
    ]
    lines.extend(_hexagon(9, "PHE", "A", 2, (0.0, 0.0, 4.5)))
    lines.extend(_hexagon(30, "PHE", "A", 5, (30.0, 30.0, 0.0)))
    return _write(tmp_path / "structure.pdb", lines)


def test_ring_geometry_helpers(tmp_path) -> None:
    form = _form(_amide_fixture(tmp_path))
    coords, resnames, atom_names, chains, numbers, labels = _fields(form)
    rings = ring_planes(coords, resnames, atom_names, labels)
    assert len(rings) == 2
    assert rings[0]["label"] == "A:PHE:2"
    assert np.allclose(rings[0]["centroid"], [0.0, 0.0, 4.5], atol=1e-6)
    assert abs(abs(rings[0]["normal"][2]) - 1.0) < 1e-6
    amides = amide_groups(coords, resnames, atom_names, labels, chains, numbers)
    assert [group["label"] for group in amides] == ["A:ALA:1"]
    assert np.allclose(amides[0]["carbon"], [0.0, 0.0, 2.4])
    assert cation_centroids(coords, resnames, atom_names, labels) == []
    assert angle_between(np.array([1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0])) == pytest.approx(90.0)


def test_amide_pi_bond_values(tmp_path) -> None:
    form = _form(_amide_fixture(tmp_path))
    step = StructureAmidePiBondsStep()
    ctx = Ctx({})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.dims == ["bond", "statistic"]
    assert out.data.shape == (1, 3)
    assert list(out.labels["bond"]) == ["A:ALA:1-A:PHE:2"]
    distance, offset, angle = out.data[0].tolist()
    assert distance == pytest.approx(2.1, abs=1e-3)
    assert offset == pytest.approx(2.1, abs=1e-3)
    assert angle == pytest.approx(180.0, abs=1e-3)
    assert out.info["n_rings"] == 2
    assert out.info["n_bonds"] == 1
    assert step.export(ctx)["n_bonds"] == 1


def test_amide_pi_helper_thresholds() -> None:
    ring = {
        "label": "A:PHE:2",
        "ring_index": 0,
        "centroid": np.array([0.0, 0.0, 4.5]),
        "normal": np.array([0.0, 0.0, 1.0]),
    }
    amide = {
        "label": "A:ALA:1",
        "carbon": np.array([0.0, 0.0, 2.4]),
        "n_bond": np.array([0.0, 0.0, -1.0]),
    }
    assert len(amide_pi_bonds([ring], [amide])) == 1
    assert amide_pi_bonds([ring], [amide], max_distance=1.0) == []
    assert amide_pi_bonds([ring], [amide], max_offset=1.0) == []
    tilted = {**amide, "n_bond": np.array([0.5, 0.0, -1.0])}
    assert amide_pi_bonds([ring], [tilted], min_angle=170.0) == []


def test_amide_pi_errors(tmp_path) -> None:
    form = _form(_amide_fixture(tmp_path))
    with pytest.raises(StepError, match="max_distance"):
        StructureAmidePiBondsStep().run(Ctx({"max_distance": 20.0}), [form])
    with pytest.raises(StepError, match="max_offset"):
        StructureAmidePiBondsStep().run(Ctx({"max_offset": 0.0}), [form])
    with pytest.raises(StepError, match="min_angle"):
        StructureAmidePiBondsStep().run(Ctx({"min_angle": 200.0}), [form])
    wrong = Form(data=form.data, dims=["atom", "other"], labels=form.labels, info=form.info)
    with pytest.raises(StepError, match="PDB form"):
        StructureAmidePiBondsStep().run(Ctx({}), [wrong])
    bare = _write(
        tmp_path / "bare.pdb",
        [
            _atom("ATOM", 1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C"),
            _atom("ATOM", 2, "CA", "GLY", "A", 2, 3.8, 0.0, 0.0, "C"),
        ],
    )
    with pytest.raises(StepError, match="no aromatic ring atoms"):
        StructureAmidePiBondsStep().run(Ctx({}), [_form(bare)])


def test_cation_pi_values(tmp_path) -> None:
    lines = _hexagon(1, "PHE", "A", 1, (0.0, 0.0, 0.0))
    lines.append(_atom("ATOM", 10, "NZ", "LYS", "A", 2, 0.0, 0.0, 1.5, "N"))
    lines.append(_atom("ATOM", 11, "CE", "LYS", "A", 2, 0.0, 0.0, 3.0, "C"))
    lines.append(_atom("ATOM", 12, "CZ", "ARG", "A", 3, 20.0, 0.0, 0.0, "C"))
    form = _form(_write(tmp_path / "cation.pdb", lines))
    step = StructureCationPiStep()
    ctx = Ctx({})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (1, 2)
    distance, offset = out.data[0].tolist()
    assert distance == pytest.approx(1.5, abs=1e-3)
    assert offset == pytest.approx(1.5, abs=1e-3)
    assert out.info["n_cations"] == 2
    with pytest.raises(StepError, match="no charged cations"):
        StructureCationPiStep().run(
            Ctx({}), [_form(_write(tmp_path / "noring.pdb", _hexagon(1, "PHE", "A", 1, (0.0, 0.0, 0.0))))]
        )
    with pytest.raises(StepError, match="max_distance"):
        StructureCationPiStep().run(Ctx({"max_distance": 1.0}), [form])
    with pytest.raises(StepError, match="max_offset"):
        StructureCationPiStep().run(Ctx({"max_offset": 0.0}), [form])
    ctx = Ctx({"max_offset": 1.0})
    StructureCationPiStep().run(ctx, [form])
    assert ctx["out"].data.shape == (0, 2)


def test_cation_pi_helper() -> None:
    ring = {
        "label": "A:PHE:1",
        "ring_index": 0,
        "centroid": np.array([0.0, 0.0, 0.0]),
        "normal": np.array([0.0, 0.0, 1.0]),
    }
    cation = {"label": "A:LYS:2", "centroid": np.array([0.0, 0.0, 1.5])}
    assert len(cation_pi_bonds([ring], [cation])) == 1
    assert cation_pi_bonds([ring], [cation], max_distance=0.5) == []


def test_stacking_parallel_and_t_shaped(tmp_path) -> None:
    lines = _hexagon(1, "PHE", "A", 1, (0.0, 0.0, 0.0))
    lines.extend(_hexagon(10, "TYR", "A", 2, (0.0, 0.0, 1.8)))
    for index, name in enumerate(["CG", "CD1", "CE1", "CZ", "CE2", "CD2"]):
        theta = math.radians(60.0 * index)
        point = (4.5, 1.4 * math.cos(theta), 1.4 * math.sin(theta))
        lines.append(_atom("ATOM", 20 + index, name, "PHE", "A", 3, *point, "C"))
    form = _form(_write(tmp_path / "stacking.pdb", lines))
    step = StructureAromaticStackingStep()
    ctx = Ctx({})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape[1] == 5
    assert out.info["n_rings"] == 3
    rows = {row["bond"]: row for row in out.info["pairs"]}
    assert rows["A:PHE:1-A:TYR:2"]["kind"] == "parallel"
    assert rows["A:PHE:1-A:PHE:3"]["kind"] == "t_shaped"
    assert out.info["parallel"] == 1
    assert out.info["t_shaped"] >= 1
    assert step.export(ctx)["n_rings"] == 3
    with pytest.raises(StepError, match="at least two aromatic rings"):
        StructureAromaticStackingStep().run(
            Ctx({}), [_form(_write(tmp_path / "one.pdb", _hexagon(1, "PHE", "A", 1, (0.0, 0.0, 0.0))))]
        )
    with pytest.raises(StepError, match="max_distance"):
        StructureAromaticStackingStep().run(Ctx({"max_distance": 1.0}), [form])
    with pytest.raises(StepError, match="parallel_angle"):
        StructureAromaticStackingStep().run(Ctx({"parallel_angle": 100.0}), [form])
