"""Tests for the v1.30.0 interface_hbond_network operator."""

from __future__ import annotations

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.step.steps.interface_hbond_network import (
    InterfaceHbondNetworkStep,
    interface_bonds,
)


def _atom(serial: int, name: str, resname: str, chain: str, number: int, x: float, y: float, z: float) -> str:
    return (
        f"ATOM  {serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.0:>6.2f}{10.0:>6.2f}          {'N' if name == 'N' else 'C':>2}"
    )


def _pdb(tmp_path):
    lines = [
        # chain A residue 1: defines the amide hydrogen direction for residue 2
        _atom(1, "N", "ALA", "A", 1, -6.5, 0.0, 0.0),
        _atom(2, "CA", "ALA", "A", 1, -6.0, 1.0, 0.0),
        _atom(3, "C", "ALA", "A", 1, -4.5, 0.0, 0.0),
        _atom(4, "O", "ALA", "A", 1, -5.5, 0.0, 0.0),
        # chain A residue 2: donor facing the acceptor of chain B
        _atom(5, "N", "ALA", "A", 2, -2.9, 0.0, 0.0),
        _atom(6, "CA", "ALA", "A", 2, -2.4, 1.0, 0.0),
        _atom(7, "C", "ALA", "A", 2, -2.4, 2.0, 0.0),
        _atom(8, "O", "ALA", "A", 2, -2.4, 3.0, 0.0),
        # chain B residue 1: acceptor carbonyl
        _atom(9, "N", "GLY", "B", 1, 0.0, 5.0, 0.0),
        _atom(10, "CA", "GLY", "B", 1, 0.5, 5.0, 0.0),
        _atom(11, "C", "GLY", "B", 1, 1.23, 0.0, 0.0),
        _atom(12, "O", "GLY", "B", 1, 0.0, 0.0, 0.0),
    ]
    path = tmp_path / "complex.pdb"
    path.write_text("HEADER    HBOND\n" + "\n".join(lines) + "\nEND\n", encoding="utf-8")
    return path


def _form(tmp_path):
    return read_source(
        _pdb(tmp_path), dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"}
    )


def test_single_interface_bond(tmp_path) -> None:
    form = _form(tmp_path)
    step = InterfaceHbondNetworkStep()
    params = {"binder_chains": "A", "target_chains": "B", "output": "bonds"}

    class Ctx(dict):
        def __init__(self, params):
            self.step_params = dict(params)
            self.metadata = {}

    ctx = Ctx(params)
    step.run(ctx, [form])
    out = ctx["bonds"]
    assert list(out.dims) == ["bond", "statistic"]
    assert out.data.shape == (1, 2)
    energy, distance = out.data[0]
    assert distance == pytest.approx(2.9, abs=1e-4)
    expected = 0.084 * 332.0 * (1 / 2.9 + 1 / 3.13 - 1 / 1.9 - 1 / 4.13)
    assert energy == pytest.approx(expected, rel=1e-4)
    label = list(out.labels["bond"])[0]
    assert label == "A:ALA:2->B:GLY:1"
    assert out.info["n_bonds"] == 1
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["B"]
    assert step.export(ctx)["n_bonds"] == 1


def test_interface_bonds_helper() -> None:
    residues = [
        {
            "chain": "A",
            "resname": "ALA",
            "label": "A:ALA:1",
            "coords": {
                "N": np.array([-6.5, 0.0, 0.0]),
                "C": np.array([-4.5, 0.0, 0.0]),
                "O": np.array([-5.5, 0.0, 0.0]),
            },
        },
        {
            "chain": "A",
            "resname": "ALA",
            "label": "A:ALA:2",
            "coords": {
                "N": np.array([-2.9, 0.0, 0.0]),
                "C": np.array([-2.4, 2.0, 0.0]),
                "O": np.array([-2.4, 3.0, 0.0]),
            },
        },
        {
            "chain": "B",
            "resname": "GLY",
            "label": "B:GLY:1",
            "coords": {
                "N": np.array([0.0, 5.0, 0.0]),
                "C": np.array([1.23, 0.0, 0.0]),
                "O": np.array([0.0, 0.0, 0.0]),
            },
        },
    ]
    rows = interface_bonds(residues, {"A"}, {"B"})
    assert len(rows) == 1
    assert rows[0]["donor"] == "A:ALA:2"
    assert rows[0]["acceptor"] == "B:GLY:1"
    assert interface_bonds(residues, {"A"}, {"B"}, energy_threshold=-10.0) == []


def test_parameter_errors(tmp_path) -> None:
    form = _form(tmp_path)
    step = InterfaceHbondNetworkStep()

    class Ctx(dict):
        def __init__(self, params):
            self.step_params = {"output": "out", **params}
            self.metadata = {}

    for params, match in [
        ({"energy_threshold": 0.5}, "energy_threshold"),
        ({"max_distance": 0.5}, "max_distance"),
        ({"binder_chains": "C"}, "chain"),
        ({"binder_chains": "A", "target_chains": "A"}, "both binder and target"),
    ]:
        with pytest.raises(StepError, match=match):
            step.run(Ctx({"binder_chains": "A", "target_chains": "B", **params}), [form])
