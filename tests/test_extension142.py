"""Tests for the interface hydrophobic patch operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.core.forms.form import Form
from src.task.step.steps.interface_hydrophobic_patch import (
    InterfaceHydrophobicPatchStep,
    _residue_groups,
    cluster_residues,
)


class _Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "patches", **params}
        self.metadata = {}


def _atom(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:5d} {name:4s} {resname:3s} {chain:1s}{number:4d}    "
        f"{x:8.3f}{y:8.3f}{z:8.3f}{1.0:6.2f}{0.0:6.2f}          {name[0]:2s}"
    )


def _pdb_form(rows: list[str]) -> Form:
    codes = np.arange(len(rows), dtype=np.float32).reshape(-1, 1)
    return Form(
        data=codes,
        dims=["atom", "row"],
        labels={"atom": {f"atom:{index}": index for index in range(len(rows))}, "row": {"id": 0}},
    )


def _structure_form(lines: list[str], tmp_path) -> Form:
    path = tmp_path / "patch.pdb"
    path.write_text("\n".join(lines) + "\nEND\n", encoding="utf-8")
    from src.reader import pick_reader

    return pick_reader(path).implementation().read(
        path, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def _fixture(tmp_path) -> Form:
    lines = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "VAL", "A", 2, 4.0, 0.0, 0.0),
        _atom(3, "CA", "LEU", "A", 3, 20.0, 0.0, 0.0),
        _atom(4, "CA", "SER", "B", 1, 0.0, 0.0, 4.0),
        _atom(5, "CA", "SER", "B", 2, 23.0, 0.0, 1.0),
    ]
    return _structure_form(lines, tmp_path)


def _run(form, params):
    ctx = _Ctx({"binder_chains": "A", "cutoff": 4.5, **params})
    step = InterfaceHydrophobicPatchStep()
    step.run(ctx, [form])
    return ctx["patches"], step.export(ctx)


def test_residue_groups_and_clustering() -> None:
    labels = np.array(["A:ALA:1", "A:ALA:1", "A:GLY:2", "B:SER:1"])
    groups = _residue_groups(labels)
    assert [label for label, _ in groups] == ["A:ALA:1", "A:GLY:2", "B:SER:1"]
    assert groups[0][1].tolist() == [0, 1]
    anchors = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0], [19.0, 0.0, 0.0]])
    assert cluster_residues(anchors, 9.5) == [[1, 2], [0]]
    assert cluster_residues(anchors, 10.0) == [[0, 1, 2]]
    assert cluster_residues(anchors, 100.0) == [[0, 1, 2]]
    assert cluster_residues(anchors, 5.0) == [[0], [1], [2]]


def test_two_separate_patches(tmp_path) -> None:
    form = _fixture(tmp_path)
    patches, exported = _run(form, {})
    assert patches.data.shape == (2, 5)
    assert list(patches.labels["patch"]) == ["patch1", "patch2"]
    assert patches.data[:, 0].tolist() == [1.0, 1.0]
    assert patches.data[:, 1].tolist() == [1.0, 1.0]
    assert patches.data[:, 2].tolist() == [1.0, 1.0]
    assert patches.data[:, 3].tolist() == [1.0, 1.0]
    assert patches.data[:, 4].tolist() == [1.0, 1.0]
    assert exported["n_patches"] == 2
    assert exported["interface_residues"] == 2
    assert patches.info["patches"][0]["residues"] == ["A:ALA:1"]
    assert patches.info["patches"][1]["residues"] == ["A:LEU:3"]


def test_wide_clustering_merges_patches(tmp_path) -> None:
    form = _fixture(tmp_path)
    patches, exported = _run(form, {"ca_cutoff": 25.0})
    assert patches.data.shape == (1, 5)
    assert patches.data[0, 0] == 2.0
    assert patches.data[0, 1] == 2.0
    assert patches.data[0, 3] == 2.0
    assert patches.data[0, 4] == 1.0
    assert exported["n_patches"] == 1


def test_min_residues_filters_singletons(tmp_path) -> None:
    form = _fixture(tmp_path)
    patches, _ = _run(form, {"min_residues": 2})
    assert patches.data.shape == (0, 5)
    assert patches.info["n_patches"] == 0


def test_target_is_derived_when_empty(tmp_path) -> None:
    form = _fixture(tmp_path)
    patches, _ = _run(form, {"target_chains": ""})
    assert patches.info["target_chains"] == ["B"]


def test_non_hydrophobic_patch(tmp_path) -> None:
    lines = [
        _atom(1, "CA", "SER", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "GLY", "B", 1, 0.0, 0.0, 4.0),
    ]
    patches, _ = _run(_structure_form(lines, tmp_path), {})
    assert patches.data[0, 1] == 0.0
    assert patches.data[0, 2] == 0.0


def test_parameter_errors(tmp_path) -> None:
    form = _fixture(tmp_path)
    with pytest.raises(StepError, match="cutoff must be"):
        _run(form, {"cutoff": 0.0})
    with pytest.raises(StepError, match="ca_cutoff must be"):
        _run(form, {"ca_cutoff": 0.0})
    with pytest.raises(StepError, match="min_residues"):
        _run(form, {"min_residues": 0})
    with pytest.raises(StepError, match="hydrophobic_resnames"):
        _run(form, {"hydrophobic_resnames": " "})


def test_wrong_dimensions_are_rejected(tmp_path) -> None:
    form = _pdb_form([_atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0)])
    ctx = _Ctx({"binder_chains": "A", "cutoff": 4.5})
    step = InterfaceHydrophobicPatchStep()
    with pytest.raises(StepError, match="a PDB form with dims"):
        step.run(ctx, [form])
