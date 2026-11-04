"""Tests for the structure packing density operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.task.step.steps._protein_common import heavy_atom_mask  # noqa: F401  (documented import)
from src.task.step.steps.structure_packing_density import (
    StructurePackingDensityStep,
    packing_rows,
    residue_centers,
)


class Ctx(dict):
    def __init__(self, params: dict) -> None:
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element="C"):
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{10.0:>6.2f}          {element:>2}"
    )


def _pdb(rows: list[str]):
    from src.reader import read_source
    import tempfile
    from pathlib import Path

    directory = Path(tempfile.mkdtemp())
    path = directory / "pack.pdb"
    path.write_text("HEADER    PACK\n" + "\n".join(rows) + "\nEND\n", encoding="utf-8")
    return read_source(path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def _run(step, params, inputs):
    ctx = Ctx(params)
    step.run(ctx, inputs)
    return ctx[ctx.step_params["output"]], step.export(ctx)


FIXTURE = [
    _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
    _atom(2, "CA", "GLY", "A", 2, 3.0, 0.0, 0.0),
    _atom(3, "CA", "THR", "A", 3, 0.0, 10.0, 0.0),
    _atom(4, "CA", "SER", "B", 1, 0.0, 0.0, 4.0),
]


def test_packing_rows_hand_computed():
    coords = np.array([[0.0, 0.0, 0.0], [3.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 4.0]])
    labels = ["A:ALA:1", "A:GLY:2", "A:THR:3", "B:SER:1"]
    centers = residue_centers(coords, labels, np.array(["CA", "CA", "CA", "CA"]))
    rows = packing_rows(coords, labels, centers, radius=5.0)
    by_label = {row[0]: row for row in rows}
    assert by_label["A:ALA:1"][1] == 3  # self, A:GLY:2 (3 A), B:SER:1 (4 A)
    assert by_label["A:GLY:2"][1] == 3  # self, A:ALA:1 (3 A), B:SER:1 (5 A)
    assert by_label["A:THR:3"][1] == 1
    assert by_label["B:SER:1"][1] == 3
    volume = 4.0 / 3.0 * np.pi * 125.0
    assert np.isclose(by_label["A:ALA:1"][3], 3.0 / volume)


def test_step_output_sorted_by_density():
    out, export = _run(StructurePackingDensityStep(), {"radius": 5.0}, [_pdb(FIXTURE)])
    assert list(out.dims) == ["residue", "statistic"]
    assert out.data.shape == (4, 3)
    labels = list(out.labels["residue"].keys())
    assert labels[0] == "A:ALA:1"
    densities = out.data[:, 2]
    assert np.all(np.diff(densities) <= 1e-6)
    assert out.info["densest_residue"] == "A:ALA:1"
    assert out.info["n_residues"] == 4
    assert export["n_residues"] == 4


def test_step_radius_changes_counts():
    form = _pdb(FIXTURE)
    small, _ = _run(StructurePackingDensityStep(), {"radius": 3.5}, [form])
    large, _ = _run(StructurePackingDensityStep(), {"radius": 12.0}, [form])
    assert small.data[small.labels["residue"]["A:ALA:1"], 0] == 2.0
    assert large.data[large.labels["residue"]["A:ALA:1"], 0] == 4.0


def test_step_water_exclusion():
    rows = FIXTURE + [_atom(5, "O", "HOH", "W", 1, 1.0, 1.0, 1.0, "O")]
    form = _pdb(rows)
    out, _ = _run(StructurePackingDensityStep(), {"radius": 5.0}, [form])
    assert "W:HOH:1" not in out.labels["residue"]
    included, _ = _run(
        StructurePackingDensityStep(), {"radius": 5.0, "exclude_resnames": ""}, [form]
    )
    assert "W:HOH:1" in included.labels["residue"]


def test_step_parameter_errors():
    form = _pdb(FIXTURE)
    with pytest.raises(StepError, match="radius must be between 2 and 20"):
        _run(StructurePackingDensityStep(), {"radius": 1.0}, [form])
    with pytest.raises(StepError, match="PDB form with dims"):
        _run(StructurePackingDensityStep(), {"atom_dim": "atoms"}, [form])
    empty = _pdb([_atom(1, "O", "HOH", "W", 1, 0.0, 0.0, 0.0, "O")])
    with pytest.raises(StepError, match="no heavy atom remains"):
        _run(StructurePackingDensityStep(), {"radius": 5.0}, [empty])
