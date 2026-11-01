"""Tests for the RDKit pharmacophore feature operator."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.core.errors import StepError
from src.task.step.steps.rdkit_pharmacophore_features import (
    RdkitPharmacophoreFeaturesStep,
    _FEATURES,
    feature_row,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "features", **params}
        self.metadata = {}


def _oracle_counts(smiles: str) -> dict[str, int]:
    from rdkit import Chem, RDConfig
    from rdkit.Chem import ChemicalFeatures

    factory = ChemicalFeatures.BuildFeatureFactory(
        __import__("os").path.join(RDConfig.RDDataDir, "BaseFeatures.fdef")
    )
    counts: dict[str, int] = {}
    for feature in factory.GetFeaturesForMol(Chem.MolFromSmiles(smiles)):
        counts[feature.GetFamily()] = counts.get(feature.GetFamily(), 0) + 1
    return counts


def test_feature_row_hand_values() -> None:
    from rdkit import Chem

    ethanol = dict(zip(_FEATURES, feature_row(Chem.MolFromSmiles("CCO"))))
    assert ethanol["donor"] == 1
    assert ethanol["acceptor"] == 1
    assert ethanol["aromatic"] == 0
    assert ethanol["total"] == 2

    benzene = dict(zip(_FEATURES, feature_row(Chem.MolFromSmiles("c1ccccc1"))))
    assert benzene["aromatic"] == 1
    assert benzene["lumped_hydrophobe"] == 1
    assert benzene["total"] == 2

    acetate = dict(zip(_FEATURES, feature_row(Chem.MolFromSmiles("CC(=O)[O-]"))))
    assert acetate["acceptor"] >= 1
    assert acetate["neg_ionizable"] == 1


def test_feature_row_matches_rdkit() -> None:
    from rdkit import Chem

    for smiles in ["CCO", "c1ccccc1", "CC(=O)[O-]", "CC[NH3+]", "c1ccncc1", "CC(=O)Oc1ccccc1C(=O)O"]:
        values = dict(zip(_FEATURES, feature_row(Chem.MolFromSmiles(smiles))))
        oracle = _oracle_counts(smiles)
        assert values["donor"] == oracle.get("Donor", 0)
        assert values["acceptor"] == oracle.get("Acceptor", 0)
        assert values["aromatic"] == oracle.get("Aromatic", 0)
        assert values["lumped_hydrophobe"] == oracle.get("LumpedHydrophobe", 0)
        assert values["pos_ionizable"] == oracle.get("PosIonizable", 0)
        assert values["neg_ionizable"] == oracle.get("NegIonizable", 0)
        assert values["total"] <= sum(oracle.values())


def test_step_output(tmp_path: Path) -> None:
    ctx = Ctx({"smiles": "CCO ethanol\nc1ccccc1 benzene\n# comment\nCC(=O)[O-]"})
    step = RdkitPharmacophoreFeaturesStep()
    step.run(ctx, [])
    out = ctx["features"]
    assert out.data.shape == (3, len(_FEATURES))
    assert out.dims == ["molecule", "feature"]
    assert list(out.labels["molecule"]) == ["ethanol", "benzene", "mol3"]
    assert list(out.labels["feature"]) == list(_FEATURES)
    assert out.info["n_molecules"] == 3
    assert step.export(ctx)["n_molecules"] == 3


def test_errors() -> None:
    with pytest.raises(StepError, match="smiles is required"):
        RdkitPharmacophoreFeaturesStep().run(Ctx({"smiles": "   "}), [])
    with pytest.raises(StepError, match="cannot parse SMILES"):
        RdkitPharmacophoreFeaturesStep().run(Ctx({"smiles": "notasmiles"}), [])
    with pytest.raises(StepError, match="without heavy atoms"):
        RdkitPharmacophoreFeaturesStep().run(Ctx({"smiles": "[H][H]"}), [])
