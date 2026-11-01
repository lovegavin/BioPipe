"""Molecular similarity, PAINS and ligand-efficiency operators (v1.23.0)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from src.core import StepError
from src.task.step.steps.ligand_efficiency import LigandEfficiencyStep, parse_activity_lines
from src.task.step.steps.pains_filter import PainsFilterStep, pain_alerts
from src.task.step.steps.rdkit_similarity import RdkitSimilarityStep

RDKIT = pytest.importorskip("rdkit")
from rdkit import Chem, DataStructs  # noqa: E402
from rdkit.Chem import Crippen, Descriptors, rdMolDescriptors  # noqa: E402


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


_SMILES = (
    "CCO ethanol\n"
    "c1ccccc1 benzene\n"
    "CC(=O)Oc1ccccc1C(=O)O aspirin\n"
    "O=C1C=CC(=O)C=C1 quinone"
)
_NAMES = ["ethanol", "benzene", "aspirin", "quinone"]


def _morgan(molecule, radius: int, n_bits: int, use_features: bool = False):
    return rdMolDescriptors.GetMorganFingerprintAsBitVect(
        molecule, radius, nBits=n_bits, useFeatures=use_features
    )


def test_similarity_matches_rdkit_tanimoto():
    out, export = _run(
        RdkitSimilarityStep(),
        {"smiles": _SMILES, "radius": 3, "n_bits": 1024},
    )
    molecules = [Chem.MolFromSmiles(line.split()[0]) for line in _SMILES.splitlines()]
    fingerprints = [_morgan(molecule, 3, 1024) for molecule in molecules]
    expected = np.zeros((4, 4))
    for row in range(4):
        for column in range(4):
            expected[row, column] = DataStructs.TanimotoSimilarity(
                fingerprints[row], fingerprints[column]
            )
    np.testing.assert_allclose(out.data, expected, rtol=1e-6, atol=1e-7)
    assert list(out.dims) == ["molecule", "molecule_b"]
    assert list(out.labels["molecule"]) == _NAMES
    assert out.labels["molecule_b"] == out.labels["molecule"]
    assert export["n_molecules"] == 4
    assert export["n_bits"] == 1024


def test_similarity_is_symmetric_with_unit_diagonal():
    out, _export = _run(RdkitSimilarityStep(), {"smiles": _SMILES})
    np.testing.assert_allclose(out.data, out.data.T, atol=1e-7)
    np.testing.assert_allclose(np.diag(out.data), 1.0, atol=1e-7)
    assert out.data[0, 1] < 0.2


def test_similarity_metrics_match_rdkit():
    molecules = [Chem.MolFromSmiles(line.split()[0]) for line in _SMILES.splitlines()]
    fingerprints = [_morgan(molecule, 2, 2048) for molecule in molecules]
    for metric, function in (
        ("dice", DataStructs.DiceSimilarity),
        ("cosine", DataStructs.CosineSimilarity),
    ):
        out, export = _run(RdkitSimilarityStep(), {"smiles": _SMILES, "metric": metric})
        assert export["metric"] == metric
        assert out.data[0, 1] == pytest.approx(
            function(fingerprints[0], fingerprints[1]), abs=1e-6
        )
        assert out.data[2, 3] == pytest.approx(
            function(fingerprints[2], fingerprints[3]), abs=1e-6
        )


def test_similarity_use_features_matches_rdkit():
    out, export = _run(RdkitSimilarityStep(), {"smiles": _SMILES, "use_features": True})
    assert export["n_molecules"] == 4
    molecules = [Chem.MolFromSmiles(line.split()[0]) for line in _SMILES.splitlines()]
    fingerprints = [_morgan(molecule, 2, 2048, use_features=True) for molecule in molecules]
    expected = DataStructs.TanimotoSimilarity(fingerprints[0], fingerprints[2])
    assert out.data[0, 2] == pytest.approx(expected, abs=1e-6)


def test_similarity_errors():
    with pytest.raises(StepError, match="molecule_dim and comparison_dim"):
        _run(RdkitSimilarityStep(), {"smiles": _SMILES, "molecule_dim": "molecule", "comparison_dim": "molecule"})
    with pytest.raises(StepError, match="radius must be between"):
        _run(RdkitSimilarityStep(), {"smiles": _SMILES, "radius": 0})
    with pytest.raises(StepError, match="n_bits must be between"):
        _run(RdkitSimilarityStep(), {"smiles": _SMILES, "n_bits": 32})
    with pytest.raises(StepError, match="metric must be"):
        _run(RdkitSimilarityStep(), {"smiles": _SMILES, "metric": "jaccard"})
    with pytest.raises(StepError, match="must contain at least one SMILES line"):
        _run(RdkitSimilarityStep(), {"smiles": ""})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitSimilarityStep(), {"smiles": "not_a_smiles mol"})


def test_pains_matches_rdkit_filter_catalog():
    from rdkit.Chem import FilterCatalog

    out, export = _run(PainsFilterStep(), {"smiles": _SMILES})
    params = FilterCatalog.FilterCatalogParams()
    params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    catalog = FilterCatalog.FilterCatalog(params)
    expected = []
    for line in _SMILES.splitlines():
        molecule = Chem.MolFromSmiles(line.split()[0])
        expected.append(len(catalog.GetMatches(molecule)))
    np.testing.assert_allclose(out.data[:, 0], np.asarray(expected, dtype=np.float32))
    assert list(out.labels["statistic"]) == ["n_alerts"]
    assert export["n_molecules"] == 4
    assert export["n_flagged"] == int(sum(1 for count in expected if count))
    assert set(out.info["alerts"]) == set(_NAMES)
    assert out.info["catalogue"] == "all"


def test_pains_catalogue_subset_matches_rdkit():
    from rdkit.Chem import FilterCatalog

    out, export = _run(PainsFilterStep(), {"smiles": _SMILES, "catalogue": "pains_a"})
    params = FilterCatalog.FilterCatalogParams()
    params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS_A)
    catalog = FilterCatalog.FilterCatalog(params)
    expected = [
        len(catalog.GetMatches(Chem.MolFromSmiles(line.split()[0])))
        for line in _SMILES.splitlines()
    ]
    np.testing.assert_allclose(out.data[:, 0], np.asarray(expected, dtype=np.float32))
    assert export["catalogue"] == "pains_a"


def test_pains_alerts_helper_lists_descriptions():
    molecules = [(name, Chem.MolFromSmiles(line.split()[0])) for name, line in zip(_NAMES, _SMILES.splitlines())]
    alerts = pain_alerts(molecules, "all")
    assert len(alerts) == 4
    assert all(isinstance(item, list) for item in alerts)
    assert any(item for item in alerts)


def test_pains_errors():
    with pytest.raises(StepError, match="catalogue must be one of"):
        _run(PainsFilterStep(), {"smiles": _SMILES, "catalogue": "brenk"})
    with pytest.raises(StepError, match="must contain at least one SMILES line"):
        _run(PainsFilterStep(), {"smiles": "   "})


_ETHANOL = "CCO 1000 ethanol\nc1ccccc1 100 benzene"
_GAS = 0.00198720425864083


def test_ligand_efficiency_matches_hand_calculation():
    out, export = _run(LigandEfficiencyStep(), {"smiles": _ETHANOL, "assay_unit": "nM"})
    labels = list(out.labels["statistic"])
    assert labels == [
        "heavy_atoms",
        "p_activity",
        "delta_g",
        "ligand_efficiency",
        "lle",
        "bei",
    ]
    ethanol = Chem.MolFromSmiles("CCO")
    heavy = ethanol.GetNumHeavyAtoms()
    weight = Descriptors.MolWt(ethanol)
    p_activity = 6.0
    delta_g = -_GAS * 298.15 * math.log(10.0) * p_activity
    row = out.data[out.labels["molecule"]["ethanol"]]
    assert row[0] == pytest.approx(float(heavy))
    assert row[1] == pytest.approx(p_activity, abs=1e-6)
    assert row[2] == pytest.approx(delta_g, rel=1e-5)
    assert row[3] == pytest.approx(-delta_g / heavy, rel=1e-5)
    assert row[4] == pytest.approx(p_activity - Crippen.MolLogP(ethanol), rel=1e-5)
    assert row[5] == pytest.approx(1000.0 * p_activity / weight, rel=1e-5)
    assert export["mean_ligand_efficiency"] == pytest.approx(
        float(np.mean([-delta_g / heavy, out.data[1, 3]])), rel=1e-4
    )
    assert out.info["assay_unit"] == "nM"
    assert out.info["n_molecules"] == 2


def test_ligand_efficiency_unit_conversion_and_temperature():
    micromolar, _export = _run(
        LigandEfficiencyStep(), {"smiles": "CCO 1.0 ethanol", "assay_unit": "uM"}
    )
    nanomolar, _export = _run(
        LigandEfficiencyStep(), {"smiles": "CCO 1000 ethanol", "assay_unit": "nM"}
    )
    np.testing.assert_allclose(micromolar.data, nanomolar.data, rtol=1e-5, atol=1e-6)

    hot, _export = _run(
        LigandEfficiencyStep(),
        {"smiles": "CCO 1000 ethanol", "temperature": 310.15},
    )
    cold, _export = _run(LigandEfficiencyStep(), {"smiles": "CCO 1000 ethanol"})
    assert abs(float(hot.data[0, 2])) > abs(float(cold.data[0, 2]))
    assert hot.data[0, 2] == pytest.approx(-_GAS * 310.15 * math.log(10.0) * 6.0, rel=1e-5)


def test_ligand_efficiency_parsing():
    entries = parse_activity_lines("# comment\nCCO 5.0 ethanol\n\nc1ccccc1 2")
    assert entries[0] == ("CCO", "ethanol", 5.0)
    assert entries[1] == ("c1ccccc1", "mol_2", 2.0)
    with pytest.raises(StepError, match="must be 'SMILES activity"):
        parse_activity_lines("CCO")
    with pytest.raises(StepError, match="is not a number"):
        parse_activity_lines("CCO strong")
    with pytest.raises(StepError, match="must be positive"):
        parse_activity_lines("CCO 0")
    with pytest.raises(StepError, match="cannot parse SMILES"):
        parse_activity_lines("qwerty 5")


def test_ligand_efficiency_errors():
    with pytest.raises(StepError, match="assay_unit must be"):
        _run(LigandEfficiencyStep(), {"smiles": _ETHANOL, "assay_unit": "M"})
    with pytest.raises(StepError, match="temperature must be between"):
        _run(LigandEfficiencyStep(), {"smiles": _ETHANOL, "temperature": 100.0})
    with pytest.raises(StepError, match="smiles is required"):
        _run(LigandEfficiencyStep(), {"smiles": ""})
