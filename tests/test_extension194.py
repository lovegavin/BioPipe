from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import pick_reader, read_source
from src.task.step.steps.structure_helix_geometry import (
    StructureHelixGeometryStep,
    ca_coordinates,
    helix_geometry,
    helix_runs,
)

AA3 = {"ALA": "A", "GLY": "G", "SER": "S"}


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float, element: str) -> str:
    line = "{:6s}{:5d} {:4s}{:1s}{:3s} {:1s}{:4d}{:1s}   {:8.3f}{:8.3f}{:8.3f}{:6.2f}{:6.2f}          {:2s}".format(
        "ATOM", serial, name, " ", resname, chain, number, " ", x, y, z, 1.0, 0.0, element
    )
    return line + "\n"


def helix_pdb(path: Path, count: int = 10, rise: float = 1.5, radius: float = 2.3, turn: float = 100.0) -> Path:
    lines = []
    serial = 1
    for index in range(count):
        angle = math.radians(index * turn)
        x = radius * math.cos(angle)
        y = radius * math.sin(angle)
        z = index * rise
        for name, offset, element in (("N", (-0.5, 0.2, -0.3), "N"), ("CA", (0.0, 0.0, 0.0), "C"), ("C", (0.5, -0.2, 0.3), "C"), ("O", (0.8, -0.4, 0.5), "O")):
            lines.append(
                _atom(
                    serial,
                    name,
                    "ALA",
                    "A",
                    index + 1,
                    x + offset[0],
                    y + offset[1],
                    z + offset[2],
                    element,
                )
            )
            serial += 1
    path.write_text("HEADER    IDEAL HELIX\n" + "".join(lines) + "END\n")
    return path


def linear_pdb(path: Path, count: int = 6) -> Path:
    lines = []
    serial = 1
    for index in range(count):
        for name, offset, element in (("N", (-0.5, 0.2, -0.3), "N"), ("CA", (0.0, 0.0, 0.0), "C"), ("C", (0.5, -0.2, 0.3), "C"), ("O", (0.8, -0.4, 0.5), "O")):
            lines.append(
                _atom(serial, name, "ALA", "A", index + 1, index * 3.8 + offset[0], offset[1], offset[2], element)
            )
            serial += 1
    path.write_text("HEADER    LINEAR\n" + "".join(lines) + "END\n")
    return path


def _form(path: Path):
    reader = pick_reader(path).implementation()
    return read_source(path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}, reader_id=reader.definition["id"])


def test_ideal_helix_geometry() -> None:
    count, rise, radius, turn = 36, 1.5, 2.3, 100.0
    points = np.asarray(
        [
            [radius * math.cos(math.radians(index * turn)), radius * math.sin(math.radians(index * turn)), index * rise]
            for index in range(count)
        ]
    )
    geometry = helix_geometry(points)
    assert geometry["n_residues"] == count
    assert geometry["rise"] == pytest.approx(rise, rel=1e-3)
    assert geometry["radius"] == pytest.approx(radius, rel=5e-3)
    assert geometry["twist_deg"] == pytest.approx(turn, rel=5e-3)
    assert geometry["residues_per_turn"] == pytest.approx(360.0 / turn, rel=5e-3)


def test_helix_runs_detects_and_rejects() -> None:
    ideal = np.asarray(
        [
            [2.3 * math.cos(math.radians(index * 100.0)), 2.3 * math.sin(math.radians(index * 100.0)), index * 1.5]
            for index in range(10)
        ]
    )
    assert helix_runs(ideal) == [(0, 10)]
    linear = np.asarray([[index * 3.8, 0.0, 0.0] for index in range(6)])
    assert helix_runs(linear) == []


def test_step_output_on_ideal_pdb(tmp_path: Path) -> None:
    path = helix_pdb(tmp_path / "helix.pdb", count=36)
    form = _form(path)
    step = StructureHelixGeometryStep()
    ctx = Ctx({})
    step.run(ctx, [form])
    out = ctx["out"]
    assert list(out.dims) == ["helix", "statistic"]
    assert list(out.labels["helix"].keys()) == ["helix1"]
    assert out.data[0].tolist() == pytest.approx([36.0, 1.5, 2.3, 100.0, 3.6], rel=5e-2)
    assert step.export(ctx)["n_helices"] == 1


def test_no_helix_gives_empty_form(tmp_path: Path) -> None:
    path = linear_pdb(tmp_path / "linear.pdb")
    step = StructureHelixGeometryStep()
    ctx = Ctx({})
    step.run(ctx, [_form(path)])
    out = ctx["out"]
    assert out.data.shape == (0, 5)
    assert out.info["n_helices"] == 0


def test_errors(tmp_path: Path) -> None:
    path = helix_pdb(tmp_path / "helix.pdb")
    with pytest.raises(StepError, match="min_length must be at least 4"):
        StructureHelixGeometryStep().run(Ctx({"min_length": 2}), [_form(path)])
    with pytest.raises(StepError, match="distance thresholds must be positive"):
        StructureHelixGeometryStep().run(Ctx({"ca_distance": 0.0}), [_form(path)])
    with pytest.raises(StepError, match="must have dims"):
        StructureHelixGeometryStep().run(Ctx({"atom_dim": "other"}), [_form(path)])
    small = tmp_path / "tiny.pdb"
    small.write_text("HEADER    TINY\n" + _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0, "C") + "END\n")
    with pytest.raises(StepError, match="at least three CA atoms"):
        StructureHelixGeometryStep().run(Ctx({}), [_form(small)])
