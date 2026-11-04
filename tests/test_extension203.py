import numpy as np
import pytest
from rdkit import Chem
from rdkit.Chem import AllChem

from src.core.errors import StepError
from src.task.step.steps.rdkit_atom_environment_histogram import (
    STATISTICS,
    RdkitAtomEnvironmentHistogramStep,
    environment_counts,
    environment_row,
)


class Ctx(dict):
    def __init__(self, params):
        super().__init__()
        self.step_params = {"output": "out", **params}
        self.metadata = {}


def _run(step, params):
    ctx = Ctx(params)
    step.run(ctx, [])
    return ctx["out"], step.export(ctx)


def test_counts_match_rdkit():
    molecule = Chem.MolFromSmiles("c1ccccc1")
    counts = environment_counts(molecule, 2)
    direct = dict(AllChem.GetMorganFingerprint(molecule, 2, useCounts=True).GetNonzeroElements())
    assert counts == direct
    row = environment_row(molecule, 2)
    assert row["n_unique"] == len(direct)
    assert row["n_environments"] == sum(direct.values())
    probabilities = np.asarray(list(direct.values()), dtype=float) / sum(direct.values())
    assert np.isclose(row["entropy"], -np.sum(probabilities * np.log2(probabilities)))


def test_step_matrix_and_info():
    smiles = "c1ccccc1 benzene\nCCO ethanol"
    out, export = _run(RdkitAtomEnvironmentHistogramStep(), {"smiles": smiles, "radius": 2})
    assert list(out.dims) == ["molecule", "statistic"]
    labels = [name for name, _ in sorted(out.labels["statistic"].items(), key=lambda item: item[1])]
    assert labels == list(STATISTICS)
    assert out.data.shape == (2, 4)
    assert out.labels["molecule"] == {"benzene": 0, "ethanol": 1}
    assert out.info["radius"] == 2
    assert [entry["name"] for entry in out.info["environments"]] == ["benzene", "ethanol"]
    assert export["mean_entropy"] > 0


def test_radius_changes_histogram():
    molecule = Chem.MolFromSmiles("CC(=O)Oc1ccccc1C(=O)O")
    one = environment_row(molecule, 1)
    two = environment_row(molecule, 2)
    assert two["n_unique"] >= one["n_unique"]
    assert two["n_environments"] > 0 and two["n_environments"] >= one["n_environments"]


def test_errors():
    with pytest.raises(StepError, match="radius must be between"):
        _run(RdkitAtomEnvironmentHistogramStep(), {"smiles": "CCO", "radius": 0})
    with pytest.raises(StepError, match="smiles is required|must contain at least one SMILES"):
        _run(RdkitAtomEnvironmentHistogramStep(), {"smiles": ""})
    with pytest.raises(StepError, match="cannot parse SMILES"):
        _run(RdkitAtomEnvironmentHistogramStep(), {"smiles": "notasmiles"})
