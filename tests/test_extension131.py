"""Tests for the backbone hydrogen-bond operator."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

from src.core.errors import StepError
from src.reader import read_source
from src.task.step.steps.structure_hbonds import (
    StructureHbondsStep,
    hbond_energy,
    hydrogen_positions,
)

FIXTURE = Path(__file__).parent / "fixtures" / "backbone_1bc8_c60_75.pdb"


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _form():
    return read_source(FIXTURE, dims=["atom", "field"], labels={"atom": "auto", "field": "builtin"})


def _run(params, form=None):
    form = form if form is not None else _form()
    ctx = Ctx(params)
    step = StructureHbondsStep()
    step.run(ctx, [form])
    return step, ctx["out"]


def _counts(form):
    data = np.asarray(form.data)
    labels = list(form.labels["residue"].keys())
    return {label: (int(data[index, 0]), int(data[index, 1])) for index, label in enumerate(labels)}


def test_backbone_bonds_match_dssp():
    _, out = _run({"energy_threshold": -0.5})
    assert list(out.dims) == ["residue", "statistic"]
    assert list(out.labels["statistic"].keys()) == ["donors", "acceptors", "min_energy"]
    assert out.data.shape[0] == 16
    counts = _counts(out)
    assert sum(donors for donors, _ in counts.values()) == 10
    assert sum(acceptors for _, acceptors in counts.values()) == 10
    assert counts["C:ARG:64"] == (1, 2)
    assert counts["C:TYR:65"] == (1, 1)
    assert counts["C:SER:60"] == (0, 1)
    assert int(out.info["n_bonds"]) == 10
    assert out.info["n_donor_residues"] == 9
    assert out.info["n_acceptor_residues"] == 7
    assert out.info["unit"] == "kcal/mol"


def test_min_energy_is_strongest_interaction():
    _, out = _run({})
    energies = np.asarray(out.data[:, 2], dtype=np.float64)
    finite = energies[np.isfinite(energies)]
    assert finite.size > 0
    assert finite.min() == pytest.approx(-2.4507, abs=1e-3)
    assert np.isfinite(energies[out.labels["residue"]["C:ARG:64"]])


def test_bonds_info_lists_energy_sorted_pairs():
    _, out = _run({})
    bonds = out.info["bonds"]
    assert len(bonds) == 10
    assert bonds == sorted(bonds, key=lambda bond: (bond[2], bond[0], bond[1]))
    donor, acceptor, energy = bonds[0]
    assert donor == "C:ARG:64"
    assert acceptor == "C:SER:60"
    assert energy < -2.0


def test_hbond_energy_matches_hand_calculation():
    class Structure:
        pass

    donor = {"coords": {"N": np.array([0.0, 0.0, 0.0]), "C": np.array([1.0, 0.0, 0.0]), "O": np.array([0.0, 1.0, 0.0])}}
    acceptor = {"coords": {"N": np.array([5.0, 5.0, 5.0]), "C": np.array([0.0, 0.0, 3.0]), "O": np.array([0.0, 0.0, 3.5])}}
    hydrogen = np.array([0.0, 0.0, -1.0])
    r_on = 3.5
    r_ch = np.linalg.norm([0.0, 0.0, 4.0])
    r_oh = np.linalg.norm([0.0, 0.0, 4.5])
    r_cn = np.linalg.norm([0.0, 0.0, 3.0])
    expected = 0.084 * 332.0 * (1 / r_on + 1 / r_ch - 1 / r_oh - 1 / r_cn)
    assert hbond_energy(donor, acceptor, hydrogen) == pytest.approx(expected, rel=1e-6)


def test_hydrogen_positions_follow_previous_carbonyl():
    residues = [
        {"chain": "A", "coords": {"C": np.array([0.0, 0.0, 0.0]), "O": np.array([1.0, 0.0, 0.0]), "N": np.array([0.0, 0.0, 1.0])}},
        {"chain": "A", "coords": {"C": np.array([0.0, 1.0, 1.0]), "O": np.array([0.0, 2.0, 1.0]), "N": np.array([0.0, 0.0, 3.0])}},
        {"chain": "B", "coords": {"C": np.array([0.0, 1.0, 1.0]), "O": np.array([0.0, 2.0, 1.0]), "N": np.array([0.0, 0.0, 3.0])}},
    ]
    hydrogens = hydrogen_positions(residues)
    assert hydrogens[0] is None
    # direction is antiparallel to the C=O bond of the previous residue
    np.testing.assert_allclose(hydrogens[1], residues[1]["coords"]["N"] + np.array([-1.0, 0.0, 0.0]))
    # chain boundaries reset the amide hydrogen
    assert hydrogens[2] is None


def test_threshold_and_inter_chain_options():
    _, loose = _run({"energy_threshold": -0.3})
    _, strict = _run({"energy_threshold": -1.5})
    assert int(loose.info["n_bonds"]) > int(strict.info["n_bonds"])
    assert int(strict.info["n_bonds"]) >= 1
    _, inter = _run({"include_inter_chain": True})
    # the fixture is a single chain, so the toggle cannot create bonds
    assert int(inter.info["n_bonds"]) == int(_run({})[1].info["n_bonds"])


def test_export_and_print(capsys):
    step, out = _run({})
    record = step.export(Ctx({}))
    assert record["residues"] == 16
    assert record["bonds"] == 10
    assert record["energy_threshold"] == -0.5
    printed = capsys.readouterr().out
    assert "structure_hbonds: 16 residues" in printed


def test_parameter_errors():
    with pytest.raises(StepError, match="energy_threshold must be negative"):
        _run({"energy_threshold": 0.5})
    with pytest.raises(StepError, match="max_distance must be between"):
        _run({"max_distance": 0.5})
    with pytest.raises(StepError, match="PDB form with dims"):
        _run({}, form=_shifted_form())


def _shifted_form():
    form = _form()
    from src.core.forms.form import Form

    return Form(data=form.data, dims=["atom", "feature"], labels={"atom": form.labels["atom"], "feature": form.labels["field"]}, info=form.info)


def test_input_errors_reject_incomplete_backbones():
    from src.core.forms.form import Form

    form = _form()
    labels = form.labels["field"]
    encoder = form.info["encoders"]["field"]["atom_name"]
    names = encoder.inverse_transform(form.data[:, labels["atom_name"]])
    keep = np.asarray([index for index, name in enumerate(names) if str(name).strip() == "CA"], dtype=np.int64)
    tiny = Form(
        data=np.asarray(form.data[keep], dtype=np.float32),
        dims=list(form.dims),
        labels={
            "atom": {f"atom:{index}": position for position, index in enumerate(keep.tolist())},
            "field": dict(labels),
        },
        info=form.info,
    )
    with pytest.raises(StepError, match="at least three residues"):
        _run({}, form=tiny)


@pytest.mark.skipif(shutil.which("mkdssp") is None, reason="mkdssp is not installed")
def test_operator_matches_mkdssp(tmp_path):
    _, out = _run({"energy_threshold": -0.55})
    counts = _counts(out)
    target = tmp_path / "fixture.dssp"
    subprocess.run(
        ["mkdssp", str(FIXTURE), str(target)],
        capture_output=True,
        text=True,
        check=True,
    )
    donors, acceptors = _parse_dssp(target.read_text(), -0.55)
    for index, label in enumerate(out.labels["residue"].keys()):
        chain, _, number = label.split(":")
        number = int(number.rstrip("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
        key = (chain, number)
        # mkdssp prints at most two partners per residue, so compare the top two
        mine = (min(counts[label][0], 2), min(counts[label][1], 2))
        expected = (min(len(donors.get(key, [])), 2), min(len(acceptors.get(key, [])), 2))
        assert mine == expected, label


def _parse_dssp(text: str, threshold: float):
    donors: dict = {}
    acceptors: dict = {}
    for line in text.splitlines():
        if not line.startswith(" ") or len(line) < 60:
            continue
        tokens = line.split()
        energies = [token for token in tokens if "," in token]
        if len(energies) < 4:
            continue
        try:
            number = int(tokens[1])
        except (IndexError, ValueError):
            continue
        key = (tokens[2], number)
        for offset, entry in enumerate(energies):
            try:
                _, value = entry.split(",")
                value = float(value)
            except ValueError:
                continue
            if value < threshold:
                bucket = donors if offset % 2 == 0 else acceptors
                bucket.setdefault(key, []).append(value)
    return donors, acceptors
