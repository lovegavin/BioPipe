"""Interface buried-surface-area operator (v1.20.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import Form, StepError
from src.reader.readers.pdb_reader import PdbReader
from src.task.step.steps.interface_bsa import (
    InterfaceBsaStep,
    sasa_per_atom,
    sphere_points,
    vdw_radii,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _atom(serial, name, resname, chain, number, x, y, z, element="C", record="ATOM"):
    return (
        f"{record:<6}{serial:>5} {name:<4} {resname:>3} {chain}{number:>4}    "
        f"{x:>8.3f}{y:>8.3f}{z:>8.3f}{1.00:>6.2f}{0.00:>6.2f}"
        f"          {element:>2}"
    )


def _pdb_form(tmp_path, atoms, name="x.pdb"):
    path = tmp_path / name
    path.write_text("\n".join(atoms) + "\nEND\n")
    reader = PdbReader()
    return reader.read(
        path,
        dims=["atom", "field"],
        labels={"atom": "auto", "field": "builtin"},
    )


def _brute_force_sasa(coords, radii, probe=1.4, n_points=92):
    """Direct O(N^2) Shrake-Rupley reference used to validate the KD-tree path."""
    unit = sphere_points(n_points)
    areas = np.zeros(len(coords), dtype=np.float64)
    for index in range(len(coords)):
        points = coords[index] + (radii[index] + probe) * unit
        free = np.ones(n_points, dtype=bool)
        for other in range(len(coords)):
            if other == index:
                continue
            distance = np.linalg.norm(points - coords[other], axis=1)
            free &= distance >= radii[other] + probe
        areas[index] = 4.0 * np.pi * (radii[index] + probe) ** 2 * free.mean()
    return areas


TWO_CHAIN = [
    _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
    _atom(2, "CA", "GLY", "A", 2, 0.0, 0.0, 4.0),
    _atom(3, "CA", "SER", "B", 1, 0.0, 0.0, 1.5),
    _atom(4, "CA", "SER", "B", 2, 0.0, 0.0, 2.5),
]


def test_isolated_atom_sasa_is_exact():
    radii = np.array([1.7])
    area = sasa_per_atom(np.zeros((1, 3)), radii, n_points=512)
    assert area[0] == pytest.approx(4.0 * np.pi * (1.7 + 1.4) ** 2, rel=1e-12)


def test_two_atom_sasa_matches_analytic_cap():
    # Both expanded spheres have radius R = 1.7 + 1.4 = 3.1 and their centres
    # are 2.0 A apart, so the blocked cap has height R - d/2 = 2.1 and the
    # accessible fraction is 1 - h / (2R) = 0.66129.
    radii = np.array([1.7, 1.7])
    coords = np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 2.0]])
    areas = sasa_per_atom(coords, radii, probe_radius=1.4, n_points=512)
    free_fraction = 1.0 - 2.1 / (2.0 * 3.1)
    expected = 4.0 * np.pi * 3.1**2 * free_fraction
    np.testing.assert_allclose(areas, expected, rtol=5e-3)


def test_interface_matches_brute_force_reference(tmp_path):
    form = _pdb_form(tmp_path, TWO_CHAIN)
    step = InterfaceBsaStep()
    ctx = Ctx({"binder_chains": "A", "target_chains": "B"})
    step.run(ctx, [form])
    out = ctx["out"]

    coords = np.array([[0, 0, 0], [0, 0, 4], [0, 0, 1.5], [0, 0, 2.5]], float)
    radii = vdw_radii(["C", "C", "C", "C"])
    complex_sasa = _brute_force_sasa(coords, radii)
    free_binder = _brute_force_sasa(coords[:2], radii[:2])
    free_target = _brute_force_sasa(coords[2:], radii[2:])
    free = np.concatenate([free_binder, free_target])
    buried = np.clip(free - complex_sasa, 0.0, None)

    labels = ["A:ALA:1", "A:GLY:2", "B:SER:1", "B:SER:2"]
    totals = {label: float(buried[i]) for i, label in enumerate(labels)}
    order = sorted(totals, key=lambda label: (-totals[label], label))

    assert out.dims == ["residue", "statistic"]
    assert list(out.labels["residue"]) == order
    rows = {label: out.data[i] for i, label in enumerate(order)}
    for label in order:
        index = labels.index(label)
        assert rows[label][0] == pytest.approx(totals[label], rel=1e-5)
        assert rows[label][1] == pytest.approx(complex_sasa[index], rel=1e-5)
    assert out.info["total_buried_area"] == pytest.approx(
        sum(totals.values()), rel=1e-5
    )
    assert out.info["binder_buried_area"] + out.info["target_buried_area"] == pytest.approx(
        out.info["total_buried_area"], rel=1e-5
    )
    assert out.info["binder_chains"] == ["A"]
    assert out.info["target_chains"] == ["B"]
    assert step.export(ctx)["interface_residues"] == 4
    assert len(totals) == 4


def test_target_only_derives_binder(tmp_path):
    form = _pdb_form(tmp_path, TWO_CHAIN)
    step = InterfaceBsaStep()
    ctx = Ctx({"target_chains": "B"})
    step.run(ctx, [form])
    assert ctx["out"].info["binder_chains"] == ["A"]
    assert ctx["out"].info["target_chains"] == ["B"]


def test_non_contacting_chains_produce_empty_output(tmp_path):
    atoms = [
        _atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0),
        _atom(2, "CA", "SER", "B", 1, 0.0, 0.0, 20.0),
    ]
    form = _pdb_form(tmp_path, atoms)
    step = InterfaceBsaStep()
    ctx = Ctx({"binder_chains": "A", "target_chains": "B"})
    step.run(ctx, [form])
    out = ctx["out"]
    assert out.data.shape == (0, 2)
    assert out.info["interface_residues"] == 0
    assert out.info["total_buried_area"] == pytest.approx(0.0)


def test_interface_errors(tmp_path):
    form = _pdb_form(tmp_path, TWO_CHAIN)
    step = InterfaceBsaStep()

    with pytest.raises(StepError, match="probe_radius must be between"):
        step.run(Ctx({"probe_radius": 0.5}), [form])
    with pytest.raises(StepError, match="n_points must be between"):
        step.run(Ctx({"n_points": 8}), [form])
    with pytest.raises(StepError, match="min_buried must be zero or positive"):
        step.run(Ctx({"binder_chains": "A", "min_buried": -1.0}), [form])

    single_chain = _pdb_form(
        tmp_path, [_atom(1, "CA", "ALA", "A", 1, 0.0, 0.0, 0.0)], name="one.pdb"
    )
    with pytest.raises(StepError, match="two chain groups are required"):
        step.run(Ctx({"binder_chains": "A"}), [single_chain])

    with pytest.raises(StepError, match="not found in the PDB form"):
        step.run(Ctx({"binder_chains": "A", "target_chains": "Z"}), [form])
    with pytest.raises(StepError, match="cannot be both binder and target"):
        step.run(Ctx({"binder_chains": "A", "target_chains": "A"}), [form])
    with pytest.raises(StepError, match="must select at least one chain"):
        step.run(Ctx({}), [form])

    hydrogen = _pdb_form(
        tmp_path,
        [
            _atom(1, "H", "ALA", "A", 1, 0.0, 0.0, 0.0, element="H"),
            _atom(2, "H", "SER", "B", 1, 0.0, 0.0, 1.5, element="H"),
        ],
        name="h.pdb",
    )
    with pytest.raises(StepError, match="no heavy atoms left"):
        step.run(Ctx({"binder_chains": "A", "target_chains": "B"}), [hydrogen])

    numeric_only = Form(
        data=np.zeros((2, 3), dtype=np.float32),
        dims=["atom", "field"],
        labels={"atom": {"a": 0, "b": 1}, "field": {"x": 0, "y": 1, "z": 2}},
        info={"missing_code": np.nan},
    )
    with pytest.raises(StepError, match="has no 'chain' column"):
        step.run(Ctx({"binder_chains": "A", "target_chains": "B"}), [numeric_only])
