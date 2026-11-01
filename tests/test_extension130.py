"""Maximum common substructure operator (v1.24.0)."""
from __future__ import annotations

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.rdkit_mcs import RdkitMcsStep, count_matches, mcs_parameters

rdkit = pytest.importorskip("rdkit")

from rdkit import Chem  # noqa: E402
from rdkit.Chem import rdFMCS  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(**params):
    step = RdkitMcsStep()
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def _rdkit_mcs(smiles_list, atom_compare="elements", bond_compare="strict", ring_only=True, complete_rings_only=False):
    params = mcs_parameters(atom_compare, bond_compare, ring_only, complete_rings_only, 30)
    mols = [Chem.MolFromSmiles(smiles) for smiles in smiles_list]
    result = rdFMCS.FindMCS(mols, params)
    return result, Chem.MolFromSmarts(result.smartsString)


def test_benzene_toluene_mcs():
    out, export = _run(smiles="c1ccccc1 benzene\nCc1ccccc1 toluene")
    assert list(out.labels["molecule"]) == ["benzene", "toluene"]
    assert out.data.shape == (2, 2)
    assert out.labels["statistic"] == {"matched_atoms": 0, "unmatched_atoms": 1}
    np.testing.assert_allclose(out.data[:, 0], [6, 6])
    np.testing.assert_allclose(out.data[:, 1], [0, 1])
    assert out.info["mcs_num_atoms"] == 6
    assert out.info["mcs_num_bonds"] == 6
    assert export["mcs_num_atoms"] == 6
    assert export["mean_matched_atoms"] == pytest.approx(6.0)


def test_matches_rdkit_oracle():
    smiles_list = ["c1ccccc1", "Cc1ccccc1", "Oc1ccccc1", "c1ccncc1"]
    for atom_compare in ("any", "elements"):
        for bond_compare in ("any", "strict"):
            for ring_only in (True, False):
                out, export = _run(
                    smiles="\n".join(smiles_list),
                    atom_compare=atom_compare,
                    bond_compare=bond_compare,
                    ring_matches_ring_only=ring_only,
                )
                result, query = _rdkit_mcs(
                    smiles_list, atom_compare, bond_compare, ring_only, False
                )
                assert export["mcs_num_atoms"] == result.numAtoms
                assert export["mcs_num_bonds"] == result.numBonds
                for index, smiles in enumerate(smiles_list):
                    molecule = Chem.MolFromSmiles(smiles)
                    matched, _count = count_matches(molecule, query)
                    assert int(out.data[index, 0]) == matched
                    assert int(out.data[index, 1]) == molecule.GetNumHeavyAtoms() - matched


def test_complete_rings_only_changes_result():
    kwargs = dict(smiles="c1ccccc1 benzene\nC1CCCCC1 cyclohexane", atom_compare="any", bond_compare="any", ring_matches_ring_only=False)
    loose, loose_export = _run(**kwargs, complete_rings_only=False)
    strict, strict_export = _run(**kwargs, complete_rings_only=True)
    assert loose_export["mcs_num_atoms"] >= strict_export["mcs_num_atoms"]
    assert int(loose.data[0, 0]) >= int(strict.data[0, 0])


def test_ring_anchor_matters_for_chain():
    smiles = "c1ccccc1 benzene\nCCCCCC hexane"
    ring_only, ring_export = _run(smiles=smiles, ring_matches_ring_only=True, bond_compare="any", atom_compare="any")
    free, free_export = _run(smiles=smiles, ring_matches_ring_only=False, bond_compare="any", atom_compare="any")
    assert free_export["mcs_num_atoms"] > ring_export["mcs_num_atoms"]
    assert int(free.data[1, 0]) == 6


def test_mcs_information_is_reported():
    out, _export = _run(smiles="c1ccccc1\nCc1ccccc1", bond_compare="strict")
    assert out.info["atom_compare"] == "elements"
    assert out.info["bond_compare"] == "strict"
    assert out.info["ring_matches_ring_only"] is True
    assert out.info["complete_rings_only"] is False
    assert out.info["timeout_seconds"] == 30
    assert out.info["n_molecules"] == 2
    assert out.info["molecules"][1]["heavy_atoms"] == 7
    assert out.info["molecules"][1]["unmatched_atoms"] == 1


def test_no_common_substructure_is_rejected():
    with pytest.raises(StepError, match="no common substructure"):
        _run(smiles="C methane\nO water")


def test_single_molecule_is_rejected():
    with pytest.raises(StepError, match="at least two molecules"):
        _run(smiles="CCO ethanol")


def test_parameters_are_validated():
    with pytest.raises(StepError, match="atom_compare must be"):
        _run(smiles="CCO\nCCN", atom_compare="strict")
    with pytest.raises(StepError, match="bond_compare must be"):
        _run(smiles="CCO\nCCN", bond_compare="orders")
    with pytest.raises(StepError, match="timeout_seconds must be between"):
        _run(smiles="CCO\nCCN", timeout_seconds=0)
    with pytest.raises(StepError, match="at least one SMILES line"):
        _run(smiles="")


def test_count_matches_helper():
    benzene = Chem.MolFromSmiles("c1ccccc1")
    query = Chem.MolFromSmarts("c1ccccc1")
    matched, matches = count_matches(benzene, query)
    assert matched == 6
    assert matches == 1
    assert count_matches(benzene, None) == (0, 0)
